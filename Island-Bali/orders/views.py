import json
from datetime import datetime
from typing import Union

from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from acquiring.utils import RussianStandard
from coffee_shop.models import City
from staff.models import Shift, Staff
from users.permissions import CanViewOrders

from .models import Orders
from .serializers import (CheckoutSerializer, GetStatusPaymentSerializer,
                          OrdersCreateSerializer, OrdersSerializer)
from .validators import validate_cafe_open_or_not

rus_standard = RussianStandard()

TAGS_ORDERS = ['Заказы']


class CreateOrderView(APIView):
    # TODO добавить пермишены и тд по необходимости

    @staticmethod
    @swagger_auto_schema(
        request_body=OrdersCreateSerializer,
        operation_description="Отправляет запрос на создание заказа на основе "
                              "корзины пользователя",
        responses={201: openapi.Response(description="Заказ успешно создан",
                                         schema=OrdersSerializer),
                   400: "Некорректный запрос"},
        tags=TAGS_ORDERS,
        operation_id="Создание заказа",
        security=[{"BearerAuth": []}]
    )
    def post(request: Request) -> Union[Response, JsonResponse]:
        user = request.user
        cart = user.cart
        staff = get_object_or_404(Staff, id=user.id)
        coffee_shop = staff.place_of_work
        if not validate_cafe_open_or_not(current_time=datetime.now().time(),
                                         coffee_shop=coffee_shop):
            return Response({'error': 'Извините.Мы закрыты. '
                                      'Бариста отдыхает'},
                            status=status.HTTP_200_OK)
        serializer = OrdersCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors)
        data = serializer.validated_data
        client_comments = data['client_comments']
        time_is_finish = str(data['time_is_finish'])
        if not time_is_finish:
            return Response(
                {
                    'error': 'Неверный формат времени. Пожалуйста используйте'
                             'формат: 2024-02-06 16:20:00'},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            datetime.strptime(time_is_finish, '%Y-%m-%d %H:%M:%S%z')
        except ValueError:
            return Response(
                {
                    'error': 'Неверный формат времени. Пожалуйста используйте'
                             'формат: 2024-02-06 16:20:00'},
                status=status.HTTP_400_BAD_REQUEST)

        if not (cart, user.is_authenticated):
            return Response({
                'error': 'Корзина не найдена или пользователь не'
                         'аутентифицирован'},
                status=status.HTTP_400_BAD_REQUEST)

        city = get_object_or_404(City, name=coffee_shop.city.name)

        if not coffee_shop:
            return JsonResponse(
                {'error': 'Пользователь не связан с кофейней'},
                status=404)

        try:
            active_shift = get_object_or_404(Shift,
                                             staff__place_of_work=coffee_shop,
                                             status_shift='Open',
                                             end_time__isnull=True)

        except Shift.DoesNotExist:
            return JsonResponse(
                {'error': 'Нет открытой смены в этой кофейне'},
                status=400)

        staff_on_shift = active_shift.staff
        if staff_on_shift is None:
            return JsonResponse({
                'error': 'На открытой смене в этой '
                         'кофейне нет сотрудников'},
                status=400)

        try:
            order = cart.send_orders_for_confirmation_to_barista(
                user=user,
                city_choose=city,
                coffee_shop=coffee_shop,
                cart=cart,
                client_comments=client_comments,
                staff=staff_on_shift,
                time_is_finish=time_is_finish
            )
            serializer = OrdersSerializer(order)
            return Response(
                {
                    "orders_send_by_barista":
                        serializer.data},
                status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response(
                {'error': 'Заказ с этой корзиной уже существует'},
                status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_description="Возвращает список всех заказов для "
                          "аутентифицированного пользователя",
    responses={200: OrdersSerializer, 400: "Bad Request"},
    tags=TAGS_ORDERS,
    operation_id="Просмотр заказов пользователя"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, CanViewOrders])
def view_orders(request):
    user = request.user
    orders = Orders.objects.filter(user=user)
    serializer = OrdersSerializer(orders, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


class CheckoutView(APIView):
    # TODO изменить логику чтобы полсе оплаты в заказе становилось
    #  оплачено и нельзя было вызвать этот метод 2 раза
    # TODO Доделать чтобы корзина отправлялась в заказ
    @swagger_auto_schema(
        request_body=CheckoutSerializer,
        operation_description="Создает заказ на основе корзины пользователя и "
                              "возвращает ссылку для оплаты заказа. "
                              "user берется из токена аутентификации",
        responses={
            201: openapi.Response(
                description="Заказ успешно оформлен",
                schema=CheckoutSerializer(),
            ),
            400: "Некорректный запрос"
        },
        tags=TAGS_ORDERS,
        operation_id="Оформление заказа и получение ссылки на оплату."
    )
    def post(self, request):
        user = {'id': request.user.id}
        serializer = CheckoutSerializer(data={"user": user})
        if serializer.is_valid():
            response_data = serializer.save()
            return Response(response_data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    request_body=GetStatusPaymentSerializer,
    operation_description="Возвращает статус оплаты заказа по его инвойсу.",
    responses={201: "Created", 400: "Bad Request"},
    tags=TAGS_ORDERS,
    operation_id="Получение статуса оплаты заказа."
)
@api_view(['POST'])
def get_status_payment_for_cart(request):
    serializer = GetStatusPaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    invoice_id = serializer.data['invoice_id']
    check_status = rus_standard.check_order(invoice_id)
    response_data = json.loads(check_status)
    payment_status = response_data.get('status', None)
    if payment_status == 'paid':
        message = 'Оплата прошла успешно'
    elif payment_status == 'created':
        message = 'Оплата создана, но еще не завершена'
    elif payment_status == 'sent':
        message = 'Оплата отправлена, но еще не завершена'
    elif payment_status == 'expired':
        message = 'Срок действия оплаты истек'
    else:
        message = 'Статус оплаты неизвестен'
    return Response({'message': message, 'payment_status': payment_status})
