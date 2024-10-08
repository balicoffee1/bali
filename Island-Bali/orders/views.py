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
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from acquiring.utils import RussianStandard
from coffee_shop.models import City
from staff.models import Shift, Staff
from users.permissions import CanViewOrders

from .models import Notification, Orders, PaymentMethod
from .serializers import (CheckoutSerializer, GetStatusPaymentSerializer, NotificationSerializer, OrderStatusUpdateSerializer, OrderTimeUpdateSerializer,
                          OrdersCreateSerializer, OrdersSerializer, OrderSerializers, PaymentSerializer)
from .validators import validate_cafe_open_or_not
from cart.models import ShoppingCart

rus_standard = RussianStandard()

TAGS_ORDERS = ['Заказы']

TIME_FORMAT_ERROR = 'Неверный формат времени. Пожалуйста используйте формат: 2024-02-06 16:20:00'


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
    @swagger_auto_schema(
        request_body=CheckoutSerializer,
        operation_description="Создает заказ на основе корзины пользователя и возвращает ссылку для оплаты заказа. Пользователь берется из токена аутентификации",
        responses={
            201: openapi.Response(
                description="Заказ успешно оформлен",
                schema=CheckoutSerializer(),
            ),
            400: "Некорректный запрос"
        },
        tags=['Orders'],
        operation_id="Оформление заказа и получение ссылки на оплату."
    )
    def post(self, request):
        user = request.user

        existing_order = Orders.objects.filter(user=user, payment_status="Pending").first()
        if existing_order:
            return Response({"error": "У вас есть неоплаченный заказ."}, status=status.HTTP_400_BAD_REQUEST)
        

        cart = ShoppingCart.objects.get(user=user, is_active=True)
        if not cart.items.exists():
            return Response({"error": "Ваша корзина пуста."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CheckoutSerializer(data={"user": {"id": user.id}})
        if serializer.is_valid():
            response_data = serializer.save()
            return Response(response_data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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




class OrderViewSet(ModelViewSet):
    queryset = Orders.objects.all()
    serializer_class = OrderSerializers
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Возвращает заказы, относящиеся к текущему пользователю"""
        return Orders.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Создание нового заказа с валидацией времени"""
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['patch'], url_path='confirm')
    def confirm_order(self, request, pk=None):
        """Подтверждение заказа бариста"""
        order = self.get_object()
        order.confirm_order(staff=request.user.staff)  
        return Response({'status': 'Заказ подтвержден'})

    @action(detail=True, methods=['patch'], url_path='cancel')
    def cancel_order(self, request, pk=None):
        """Отмена заказа бариста с указанием причины"""
        order = self.get_object()
        reason = request.data.get('reason', 'Не указана')
        order.cancel_order(reason)
        return Response({'status': 'Заказ отменен'})

    @action(detail=True, methods=['patch'], url_path='update-time')
    def update_time(self, request, pk=None):
        """Изменение времени получения заказа"""
        order = self.get_object()
        serializer = OrderTimeUpdateSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'status': 'Время заказа обновлено'})

    @action(detail=True, methods=['patch'], url_path='complete')
    def complete_order(self, request, pk=None):
        """Завершение заказа бариста"""
        order = self.get_object()
        order.complete_order()
        return Response({'status': 'Заказ завершен'})

    @action(detail=True, methods=['post'], url_path='pay')
    def pay_order(self, request, pk=None):
        """Обработка оплаты заказа"""
        order = self.get_object()
        serializer = PaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment_method = serializer.validated_data['payment_method']
        order.process_payment(PaymentMethod(payment_method))
        return Response({'status': 'Оплата обработана'})


# ViewSet для уведомлений
class NotificationViewSet(ReadOnlyModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Возвращает уведомления, относящиеся к текущему пользователю"""
        return Notification.objects.filter(user=self.request.user)


# Обработка статуса заказа (через отдельный APIView)
class OrderStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        """Обновление статуса заказа (например, изменение на 'Выполняется')"""
        order = get_object_or_404(Orders, pk=pk, user=request.user)
        serializer = OrderStatusUpdateSerializer(order, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'Статус заказа обновлен'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Обработка оплаты (через отдельный APIView)
class PaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Процесс оплаты заказа"""
        order = get_object_or_404(Orders, pk=pk, user=request.user)
        serializer = PaymentSerializer(data=request.data)
        if serializer.is_valid():
            payment_method = serializer.validated_data['payment_method']
            order.process_payment(PaymentMethod(payment_method))
            return Response({'status': 'Оплата обработана'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)