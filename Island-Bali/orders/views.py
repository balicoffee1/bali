import json
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
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from acquiring.clients import RussianStandard
from coffee_shop.models import City
from staff.models import Shift, Staff
from staff.utils import is_staff_for_order
from users.permissions import CanViewOrders

from .models import Notification, Orders, CheckOrder
from .serializers import (CheckoutSerializer, GetStatusPaymentSerializer, NotificationSerializer, OrderStatusUpdateSerializer, OrderTimeUpdateSerializer,
                          OrdersCreateSerializer, OrdersSerializer, OrderSerializers, PaymentSerializer, CheckOrderSerializer)
# from .validators import validate_cafe_open_or_not
from .state_machine import OrderTransitionError
from cart.models import ShoppingCart
from users.models import CustomUser
from notifications.main import send_push_notification

rus_standard = RussianStandard()

TAGS_ORDERS = ['Заказы']

TIME_FORMAT_ERROR = 'Неверный формат времени. Пожалуйста используйте формат: 2024-02-06 16:20:00'


def _transition_error_response(exc: OrderTransitionError):
    http_status = status.HTTP_400_BAD_REQUEST
    if exc.code == "forbidden":
        http_status = status.HTTP_403_FORBIDDEN
    return Response({"error": exc.code, "message": exc.message}, status=http_status)


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
    orders = Orders.objects.filter(user=user).order_by('-created_at')
    serializer = OrdersSerializer(orders, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


class CheckoutView(APIView):
    """
    NB (обнаружено при пере-верификации M2, не входит в скоуп M0/M1):
    CheckoutSerializer.create() вызывает
    cart.send_orders_for_confirmation_to_barista(user=..., city_choose=...,
    coffee_shop=..., client_comments=..., cart=...) без обязательных
    аргументов staff/time_is_finish метода в cart/models.py — вызов упадёт
    с TypeError при любом реальном запросе. Мобильное приложение (Flutter)
    этот endpoint (`checkout/`) НЕ вызывает — реальное создание заказа идёт
    через POST /api/orders/orders/ (OrderViewSet.perform_create, ниже),
    подтверждено grep'ом по happy_island. Т.к. эндпоинт не используется и
    его починка потребовала бы придумывать недостающие staff/time_is_finish
    (unrelated redesign), он оставлен как есть, с этим комментарием — см.
    финальный отчёт §F ("предсуществующие баги вне мобильного контракта").
    """
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
        user = self.request.user
        return Orders.objects.filter(user=user)

    def perform_create(self, serializer):
        """Создание нового заказа с валидацией времени"""
        cart = ShoppingCart.objects.get(user=self.request.user, is_active=True)
        serializer.save(user=self.request.user, cart=cart, isTimeChangedDialog=True)

    def update(self, request, *args, **kwargs):
        """
        P0 (mass assignment): OrderSerializers не помечает status_orders/
        payment_status как read_only, а голый PUT/PATCH сюда (в отличие от
        именованных @action ниже) не проходит через OrderStateService —
        владелец заказа мог напрямую выставить себе Completed/Paid или
        воскресить отменённый заказ. Мобильное приложение этот путь не
        использует (все PATCH идут на именованные /cancel/, /confirm/,
        /complete/, /pay/, /client_confirmation/, /update-time/,
        /staff-update/), поэтому голый update/partial_update отключён
        целиком, а не point-fix'ится per-field.
        """
        return Response(
            {'error': 'Прямое обновление заказа не поддерживается. '
                      'Используйте /cancel/, /confirm/, /complete/, /pay/, '
                      '/client_confirmation/, /update-time/ или /staff-update/.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=['patch'], url_path='confirm')
    def confirm_orders(self, request, pk=None):
        """
        Подтверждение заказа бариста.

        M0 (P0, IDOR): раньше — `Orders.objects.get(pk=pk)` без какой-либо
        проверки, что request.user вообще сотрудник; `order.confirm_order`
        (удалён в M1) писал status_orders напрямую. Мобильное приложение
        (happy_island) этот endpoint не вызывает — staff-приёмка заказа у
        него идёт через /api/staff/ (см. staff/views.py::PendingOrdersAcceptView),
        но endpoint остаётся маршрутизируемым, поэтому закрыт тем же
        способом, что и его staff-аналог.
        """
        order = get_object_or_404(Orders, pk=pk)
        if not is_staff_for_order(request.user, order):
            return Response({'error': 'Вы не являетесь сотрудником этой кофейни'}, status=status.HTTP_403_FORBIDDEN)

        from orders.services import OrderStateService

        try:
            order = OrderStateService.accept(order.id, staff_user=request.user)
        except OrderTransitionError as exc:
            return _transition_error_response(exc)
        return Response({'status': 'Заказ подтвержден'})

    @action(detail=True, methods=['patch'], url_path='cancel')
    def cancel_orders(self, request, pk=None):
        """
        Отмена заказа клиентом.

        M0 (P0, IDOR): раньше — `Orders.objects.get(pk=pk)` без фильтрации
        по владельцу (в обход get_queryset()) — любой аутентифицированный
        пользователь мог отменить ЧУЖОЙ заказ, зная его id. Это активно
        используемый мобильным приложением endpoint (cart_repository.dart:
        PATCH /api/orders/orders/<id>/cancel/), поэтому это реальный P0, а
        не теоретический риск.
        """
        order = get_object_or_404(Orders, pk=pk)
        if order.user_id != request.user.id:
            return Response({'error': 'Вы не можете отменить этот заказ'}, status=status.HTTP_403_FORBIDDEN)

        reason = request.data.get('reason', 'Не указана')

        from orders.services import OrderStateService

        try:
            OrderStateService.cancel(order.id, actor_type="customer", reason=reason)
        except OrderTransitionError as exc:
            return _transition_error_response(exc)
        return Response({'status': 'Заказ отменен'})

    @action(detail=True, methods=['patch'], url_path='update-time')
    def update_time(self, request, pk=None):
        """Изменение времени получения заказа (get_object() уже скоупит по владельцу)."""
        order = self.get_object()
        serializer = OrderTimeUpdateSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'status': 'Время заказа обновлено'})

    @action(detail=True, methods=['patch'], url_path='complete')
    def complete_order(self, request, pk=None):
        """
        Не используется мобильным приложением (staff-завершение заказа идёт
        через /api/staff/complete_order/). get_object() скоупит по владельцу
        заказа — оставлено так же, как было, чтобы не менять модель
        авторизации незадействованного endpoint'а; исправлен только вызов
        удалённого order.complete_order().
        """
        order = self.get_object()

        from orders.services import OrderStateService

        try:
            order = OrderStateService.complete(order.id, staff_user=None)
        except OrderTransitionError as exc:
            return _transition_error_response(exc)
        return Response({'status': 'Заказ завершен'})

    @action(detail=True, methods=['post'], url_path='pay')
    def pay_order(self, request, pk=None):
        """
        Не используется мобильным приложением (реальный платёжный флоу —
        create_invoice/check_lifepay_status/lifepay webhook, acquiring/views.py).
        Раньше вызывал `order.process_payment(PaymentMethod(payment_method))` —
        оба удалены в M1, endpoint был полностью нерабочим (ImportError).
        Теперь помечает начало попытки оплаты через OrderStateService, не
        восстанавливая несуществующую реализацию под конкретный payment_method.
        """
        order = self.get_object()
        serializer = PaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment_method = serializer.validated_data['payment_method']

        from orders.services import OrderStateService

        try:
            OrderStateService.payment_started(order.id, provider=payment_method)
        except OrderTransitionError as exc:
            return _transition_error_response(exc)
        return Response({'status': 'Оплата начата'})

    @action(detail=True, methods=['post'], url_path='client_confirmation')
    def client_confirmation(self, request, pk=None):
        """Подтверждение заказа клиентом (используется мобильным приложением)."""
        order = self.get_object()
        if order.user != request.user:
            return Response({'error': 'Вы не можете подтвердить этот заказ'}, status=status.HTTP_403_FORBIDDEN)

        from orders.services import OrderStateService

        try:
            OrderStateService.client_confirmed(order.id, user=request.user)
        except OrderTransitionError as exc:
            return _transition_error_response(exc)
        return Response({'status': 'Заказ подтвержден клиентом'})

    @action(detail=True, methods=['patch'], url_path='staff-update')
    def staff_update(self, request, pk=None):
        """
        Обновление заказа со стороны сотрудника — только presentation/
        операционные поля (см. StaffOrderUpdateSerializer, M0 п.3.3);
        status_orders/payment_status этим путём больше недостижимы.
        Не используется мобильным приложением; scoping добавлен для defense
        in depth.
        """
        from orders.serializers import StaffOrderUpdateSerializer
        order = get_object_or_404(Orders, pk=pk)
        if not is_staff_for_order(request.user, order):
            return Response({'error': 'Вы не являетесь сотрудником этой кофейни'}, status=status.HTTP_403_FORBIDDEN)

        serializer = StaffOrderUpdateSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({'status': 'Заказ обновлен сотрудником', 'order': serializer.data})


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
    """
    Не используется мобильным приложением. Раньше принимал произвольное
    status_orders и писал его через ModelSerializer.save() — заказ был
    ограничен владельцем (get_object_or_404(user=request.user)), но клиент
    мог, например, сам выставить себе "Completed"/поставить оплату задним
    числом, минуя реальный флоу. Теперь допустимы только переходы, для
    которых у клиента есть легитимный именованный сценарий (Canceled ->
    отмена своего заказа); остальные значения отклоняются.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        order = get_object_or_404(Orders, pk=pk, user=request.user)
        serializer = OrderStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        target_status = serializer.validated_data['status_orders']

        from orders.services import OrderStateService

        try:
            if target_status == Orders.CANCELED:
                OrderStateService.cancel(order.id, actor_type="customer", reason="Отменено через OrderStatusUpdateView")
            else:
                return Response(
                    {"error": f"Клиент не может напрямую установить статус {target_status}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except OrderTransitionError as exc:
            return _transition_error_response(exc)

        return Response({'status': 'Статус заказа обновлен'})


# Обработка оплаты (через отдельный APIView)
class PaymentView(APIView):
    """Не используется мобильным приложением — см. комментарий к OrderViewSet.pay_order."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = get_object_or_404(Orders, pk=pk, user=request.user)
        serializer = PaymentSerializer(data=request.data)
        if serializer.is_valid():
            payment_method = serializer.validated_data['payment_method']

            from orders.services import OrderStateService

            try:
                OrderStateService.payment_started(order.id, provider=payment_method)
            except OrderTransitionError as exc:
                return _transition_error_response(exc)
            return Response({'status': 'Оплата начата'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CheckOrderViewSet(ModelViewSet):
    queryset = CheckOrder.objects.all()
    serializer_class = CheckOrderSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'coffee_shop',
                openapi.IN_QUERY,
                description="ID кофейни для фильтрации чеков",
                type=openapi.TYPE_INTEGER
            )
        ],
        operation_description="Возвращает список чеков, отфильтрованных по кофейне.",
        responses={200: CheckOrderSerializer(many=True)},
        tags=["Чеки"]
    )
    def list(self, request, *args, **kwargs):
        """
        Возвращает список чеков, отфильтрованных по coffee_shop, если параметр передан.
        """
        coffee_shop_id = self.request.query_params.get('coffee_shop', None)
        queryset = self.queryset

        if coffee_shop_id:
            queryset = queryset.filter(coffee_shop_id=coffee_shop_id)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class UpdateThankYouDialogView(APIView):
    """
    API для обновления поля isThankYouDialogOpen (UI-флаг, не входит ни в
    одну из двух state machine). Используется мобильным приложением
    (review_repository.dart). M0 (IDOR): раньше не проверял владельца заказа —
    любой аутентифицированный пользователь мог переключить этот флаг у
    чужого заказа.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):
        order = get_object_or_404(Orders, id=order_id, user=request.user)
        is_open = request.data.get('isThankYouDialogOpen')
        if is_open is not None:
            order.isThankYouDialogOpen = is_open
            order.save(update_fields=["isThankYouDialogOpen"])
            return Response({'message': 'Поле isThankYouDialogOpen обновлено'}, status=status.HTTP_200_OK)
        return Response({'error': 'Поле isThankYouDialogOpen не указано'}, status=status.HTTP_400_BAD_REQUEST)


class UpdateOrderCancelledView(APIView):
    """
    API для обновления поля isOrderCancelled (UI-флаг "показать пользователю,
    что заказ отменён" — отдельно от status_orders=Canceled). Используется
    мобильным приложением (review_repository.dart). M0 (IDOR): то же
    исправление, что и в UpdateThankYouDialogView.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):
        order = get_object_or_404(Orders, id=order_id, user=request.user)
        is_cancelled = request.data.get('isOrderCancelled')
        if is_cancelled is not None:
            order.isOrderCancelled = is_cancelled
            order.save(update_fields=["isOrderCancelled"])
            return Response({'message': 'Поле isOrderCancelled обновлено'}, status=status.HTTP_200_OK)
        return Response({'error': 'Поле isOrderCancelled не указано'}, status=status.HTTP_400_BAD_REQUEST)


class SendNotifications(APIView):
    """API для отправки уведомлений"""
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        order = get_object_or_404(Orders, id=order_id)
        if not is_staff_for_order(request.user, order):
            return Response({'error': 'Вы не являетесь сотрудником этой кофейни'}, status=status.HTTP_403_FORBIDDEN)
        message = request.data.get("message")
        send_push_notification(order.user, "Новое сообщение", message)
        return Response({'message': 'Уведомление отправлено'}, status=status.HTTP_200_OK)
