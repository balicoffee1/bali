import logging

import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from coffee_shop.models import CoffeeShop
from orders.models import Orders
from orders.state_machine import OrderTransitionError

from .clients import AlphaBankClient, RussianStandard, TinkoffClient, RSBClient
from .models import LifepayInvoice
from .providers import get_lifepay_transaction_status
from .serializers import PaymentRequestSerializer, PaymentResponseSerializer, RSBTransactionSerializer

logger = logging.getLogger("acquiring.views")

LIFEPAY_API_URL = "https://api.life-pay.ru/v1/bill"


def _transition_error_response(exc: OrderTransitionError, *, not_found_code="order_closed"):
    http_status = status.HTTP_400_BAD_REQUEST
    if exc.code == "forbidden":
        http_status = status.HTTP_403_FORBIDDEN
    return Response({"error": exc.code, "message": exc.message}, status=http_status)


# Создание ссылки для оплаты через Russian Standard
# M0 п.3.1: этот и остальные RussianStandard/Alpha/Tinkoff/RSB view'ы ниже не были
# затронуты M0/M1 предметно (не используются мобильным приложением — см. финальный
# отчёт, раздел F) — они лишь перестали быть AllowAny благодаря флипу
# DEFAULT_PERMISSION_CLASSES в island_bali/settings.py. IDOR по coffee_shop_id
# (любой аутентифицированный пользователь может дёрнуть банковские креды любой
# кофейни) в этих view остаётся задокументированным известным риском вне
# текущего скоупа (see final report §I).
class RussianStandardPaymentView(APIView):
    @swagger_auto_schema(
        request_body=PaymentRequestSerializer,
        responses={200: PaymentResponseSerializer, 400: "Invalid data."},
        operation_description="Создание ссылки для оплаты через Russian Standard"
    )
    def post(self, request, coffee_shop_id, *args, **kwargs):
        coffee_shop = CoffeeShop.objects.get(id=coffee_shop_id)
        rus_standard = RussianStandard(
            user=coffee_shop.bank_user,
            password=coffee_shop.bank_password
        )

        serializer = PaymentRequestSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            payment = rus_standard.link_for_payment(
                pay_amount=data['amount'],
                client_id=data['client_id'],
                order_id=data['order_id'],
                client_email=data['client_email'],
                service_name=data['service_name'],
                client_phone=data['client_phone']
            )
            response_serializer = PaymentResponseSerializer(payment)
            return Response(data=response_serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Проверка статуса заказа через Russian Standard
class RussianStandardCheckPaymentView(APIView):
    @swagger_auto_schema(
        responses={200: openapi.Response('Статус заказа', openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={'status': openapi.Schema(type=openapi.TYPE_STRING)}
        ))},
        operation_description="Проверка статуса заказа через Russian Standard"
    )
    def get(self, request, coffee_shop_id, invoice_id, *args, **kwargs):
        coffee_shop = CoffeeShop.objects.get(id=coffee_shop_id)
        rus_standard = RussianStandard(
            user=coffee_shop.bank_user,
            password=coffee_shop.bank_password
        )

        check_status = rus_standard.check_order(invoice_id)
        return Response(data={"status": check_status})


# Создание платежного заказа через AlphaBank
class AlphaCreatePaymentOrderView(APIView):
    @swagger_auto_schema(
        request_body=PaymentRequestSerializer,
        responses={201: openapi.Response('Успешное создание платежа', openapi.Schema(type=openapi.TYPE_OBJECT))},
        operation_description="Создание платежного заказа через AlphaBank"
    )
    def post(self, request, coffee_shop_id, *args, **kwargs):
        coffee_shop = CoffeeShop.objects.get(id=coffee_shop_id)
        client = AlphaBankClient(api_token=coffee_shop.bank_api_token)
        payment_data = request.data

        try:
            response = client.create_payment_order(payment_data)
            return Response(response, status=status.HTTP_201_CREATED)
        except requests.exceptions.HTTPError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Получение статуса платежа через AlphaBank
class AlphaGetPaymentStatusView(APIView):
    @swagger_auto_schema(
        responses={200: openapi.Response('Статус платежа', openapi.Schema(type=openapi.TYPE_OBJECT, properties={'status': openapi.Schema(type=openapi.TYPE_STRING)}))},
        operation_description="Получение статуса платежа через AlphaBank"
    )
    def get(self, request, coffee_shop_id, external_id, *args, **kwargs):
        coffee_shop = CoffeeShop.objects.get(id=coffee_shop_id)
        client = AlphaBankClient(api_token=coffee_shop.bank_api_token)

        try:
            status_response = client.get_payment_status(external_id)
            return Response(status_response, status=status.HTTP_200_OK)
        except requests.exceptions.HTTPError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Создание заказа через Тинькофф
class TBCreateOrderView(APIView):
    @swagger_auto_schema(
        request_body=PaymentRequestSerializer,
        responses={201: openapi.Response('Создание заказа', openapi.Schema(type=openapi.TYPE_OBJECT))},
        operation_description="Создание заказа через Тинькофф"
    )
    def post(self, request, coffee_shop_id, *args, **kwargs):
        coffee_shop = CoffeeShop.objects.get(id=coffee_shop_id)
        client = TinkoffClient(
            api_token=coffee_shop.bank_api_token,
            shop_id=coffee_shop.bank_shop_id
        )
        order_data = request.data

        try:
            response = client.create_order(order_data)
            return Response(response, status=status.HTTP_201_CREATED)
        except requests.exceptions.HTTPError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Получение информации о заказе через Тинькофф
class TBGetOrderView(APIView):
    @swagger_auto_schema(
        responses={200: openapi.Response('Информация о заказе', openapi.Schema(type=openapi.TYPE_OBJECT))},
        operation_description="Получение информации о заказе через Тинькофф"
    )
    def get(self, request, coffee_shop_id, order_id, *args, **kwargs):
        coffee_shop = CoffeeShop.objects.get(id=coffee_shop_id)
        client = TinkoffClient(
            api_token=coffee_shop.bank_api_token,
            shop_id=coffee_shop.bank_shop_id
        )

        try:
            order = client.get_order(order_id)
            return Response(order, status=status.HTTP_200_OK)
        except requests.exceptions.HTTPError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Транзакция через RSB
class RSBTransactionView(APIView):
    @swagger_auto_schema(
        request_body=RSBTransactionSerializer,
        responses={200: openapi.Response('Транзакция успешна', openapi.Schema(type=openapi.TYPE_OBJECT)),
                   400: openapi.Response('Ошибка транзакции', openapi.Schema(type=openapi.TYPE_OBJECT))},
        operation_description="Транзакция через RSB"
    )
    def post(self, request, coffee_shop_id, *args, **kwargs):
        coffee_shop = CoffeeShop.objects.get(id=coffee_shop_id)
        rsb_client = RSBClient(
            user=coffee_shop.bank_user,
            password=coffee_shop.bank_password
        )

        serializer = RSBTransactionSerializer(data=request.data)
        if serializer.is_valid():
            command = serializer.validated_data['command']
            amount = serializer.validated_data['amount']
            currency = serializer.validated_data['currency']
            description = serializer.validated_data['description']

            response = rsb_client.send_request(
                command=command,
                amount=amount,
                currency=currency,
                description=description
            )

            if response["success"]:
                return Response({"status": "success", "data": response["data"]})
            else:
                return Response({"status": "error", "message": response["error"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "status": "error",
            "message": "Invalid data.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class SBPPaymentCreateView(APIView):
    """
    M0/M1: раньше этот endpoint безусловно и без проверки владения ставил
    заказу COMPLETED+PAID одним `order.save()` — по факту "бесплатная оплата
    любого чужого заказа одним POST-запросом" (см. docs/order-status-websocket-audit.md,
    P0). Реальной интеграции с провайдером СБП в проекте нет (нет клиента,
    аналогичного AlphaBankClient/TinkoffClient) — придумывать её не входит в
    скоуп M0/M1. Мобильное приложение этот endpoint не вызывает (SBPRepositoryImpl
    использует только create-invoice/ и /api/payment/lifepay/status/<id>/ — см.
    финальный отчёт §F), поэтому здесь применяется тот же минимальный набор
    исправлений, что и к остальным неиспользуемым provider-view: закрыть IDOR,
    убрать прямую мутацию статуса, не выдавать false PAID.
    """

    def post(self, request, order_id, *args, **kwargs):
        try:
            order = Orders.objects.get(id=order_id)
        except Orders.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        if order.user_id != request.user.id:
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        from orders.services import OrderStateService

        try:
            OrderStateService.payment_started(order_id, provider="sbp")
        except OrderTransitionError as exc:
            return _transition_error_response(exc)

        return Response({"status": "payment_started"}, status=status.HTTP_200_OK)


@api_view(['POST'])
def create_invoice(request):
    """
    Создание счета через LifePay и сохранение инвойса.

    M0: раньше был доступен без владения заказом (любой аутентифицированный
    пользователь мог создать инвойс на чужой order_id) и содержал
    `order.status = 'pending'` — несуществующее поле модели (реальное поле —
    status_orders/payment_status), т.е. "пометка оплаты начатой" тихо ничего
    не сохраняла в БД (docs/order-status-websocket-audit.md, P1). Теперь
    владение проверяется, а факт начала оплаты фиксируется через
    OrderStateService.payment_started (единая точка мутации, M1).

    Контракт с мобильным приложением (SBPRepositoryImpl.getPaymentUrl)
    сохранён без изменений: POST {order_id} -> {"payment_url": "..."}.
    """
    order_id = request.data.get('order_id')
    try:
        order = Orders.objects.get(id=order_id)
    except Orders.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)

    if order.user_id != request.user.id:
        return Response({"error": "Forbidden"}, status=403)

    coffee_shop = order.coffee_shop

    from orders.services import OrderStateService

    try:
        OrderStateService.payment_started(order.id, provider="lifepay")
    except OrderTransitionError as exc:
        return _transition_error_response(exc)

    data = {
        "apikey": coffee_shop.lifepay_api_key,
        "login": coffee_shop.lifepay_login,
        "amount": str(order.full_price),
        "description": f"Оплата заказа #{order.id}",
        "customer_phone": str(order.user.login).replace("+", "") if order.user else None,
        "customer_email": order.user.email if order.user else None,
        "method": "sbp",
        "callback_url": "http://79.174.81.151/api/lifepay/callback/"
    }

    try:
        # verify=False (было в исходном коде) отключал проверку TLS-сертификата
        # LifePay — убрано как отдельная security-проблема, не связанная с
        # флоу состояний, но обнаруженная при аудите этого метода.
        response = requests.post(LIFEPAY_API_URL, json=data, timeout=10)
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("create_invoice: lifepay request failed order=%s error=%s", order.id, exc)
        return Response({"error": "LifePay unavailable"}, status=502)

    if result.get("code") == 0:
        invoice_data = result["data"]
        LifepayInvoice.objects.create(
            user=request.user,
            order=order,
            transaction_number=invoice_data["number"],
            payment_url=invoice_data["paymentUrl"],
            payment_url_web=invoice_data["paymentUrlWeb"]
        )
        return Response({"payment_url": invoice_data["paymentUrlWeb"]})
    else:
        return Response({"error": result.get("message")}, status=400)


def _apply_verified_lifepay_status(invoice, verified_status):
    """
    Общая точка для lifepay_callback и LifePayCallbackView (M0 п.3.4): статус
    из тела webhook'а НИКОГДА не применяется напрямую — у LifePay нет
    задокументированного механизма подписи callback'а (не найден в доступной
    документации/схеме CoffeeShop — только lifepay_api_key/lifepay_login, без
    webhook secret), поэтому вместо изобретения криптографической схемы
    каждый входящий webhook только triggers перепроверку статуса напрямую
    через API LifePay (acquiring.providers.get_lifepay_transaction_status).
    Именно verified_status (а не тело запроса) передаётся в OrderStateService.
    """
    from acquiring.providers import FAILED, NOT_FOUND, PAID, PENDING
    from orders.services import OrderStateService

    order = invoice.order
    event_key = f"{invoice.transaction_number}:{verified_status.raw_status_code}"

    if verified_status.normalized_status == PAID:
        OrderStateService.payment_succeeded(
            order.id,
            provider="lifepay",
            provider_transaction_id=invoice.transaction_number,
            provider_paid_at=verified_status.provider_paid_at,
            event_key=event_key,
        )
    elif verified_status.normalized_status == FAILED:
        OrderStateService.payment_failed(
            order.id,
            provider="lifepay",
            provider_transaction_id=invoice.transaction_number,
            reason="lifepay_webhook_failed",
            event_key=event_key,
        )
        OrderStateService.cancel(order.id, actor_type="system", reason="LifePay сообщил об отмене/просрочке платежа.")
    # PENDING / NOT_FOUND: намеренно no-op — ждём следующего события или
    # Celery-таймаут (evaluate_payment_deadline_task/finalize_payment_window_task).


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def lifepay_callback(request):
    """
    Обработка callback от LifePay для обновления статуса заказа.

    AllowAny обязателен: это входящий webhook внешнего провайдера, у него нет
    JWT нашего пользователя. Доверие обеспечивается не аутентификацией
    запроса, а перепроверкой статуса через API LifePay — см.
    _apply_verified_lifepay_status.
    """
    try:
        payload = request.data
        number = payload.get("number")
        if not number:
            return JsonResponse({"error": "Invalid data"}, status=400)

        try:
            invoice = LifepayInvoice.objects.select_related('order', 'order__coffee_shop').get(transaction_number=number)
        except LifepayInvoice.DoesNotExist:
            return JsonResponse({"error": "Invoice not found"}, status=404)

        verified_status = get_lifepay_transaction_status(invoice.order.coffee_shop, number)
        _apply_verified_lifepay_status(invoice, verified_status)
        return JsonResponse({"message": "Status updated"})

    except OrderTransitionError as exc:
        # Не 5xx: провайдер не должен ретраить webhook бесконечно из-за
        # доменной ошибки (например, заказ уже в терминальном статусе) —
        # OrderStateService уже безопасно обработал late-payment сценарий.
        logger.info("lifepay_callback: %s", exc.code)
        return JsonResponse({"message": "Acknowledged", "detail": exc.code})
    except Exception as e:
        logger.exception("lifepay_callback: unexpected error")
        return JsonResponse({"error": str(e)}, status=500)


@api_view(['GET'])
def get_lifepay_invoice_view(request):
    from .serializers import LifepayInvoiceSerializer
    """
    Получение инвойса LifePay для заказа через API.
    """
    invoice = LifepayInvoice.objects.filter(user=request.user)
    serializer = LifepayInvoiceSerializer(invoice, many=True)
    if serializer.data:
        return Response(serializer.data, status=200)
    else:
        return Response([], status=404)


class LifePayCallbackView(APIView):
    """
    Второй, дублирующий, но фактически используемый (см. callback_url в
    create_invoice: http://.../api/lifepay/callback/) обработчик callback'а
    LifePay. Прежде — та же проблема, что и в lifepay_callback: слепо
    доверял телу запроса. Теперь оба обработчика используют одну и ту же
    верифицированную точку входа _apply_verified_lifepay_status.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        data = request.data.get("data", {})

        for transaction_number, _info in data.items():
            try:
                invoice = LifepayInvoice.objects.select_related('order', 'order__coffee_shop').filter(
                    transaction_number=transaction_number
                ).first()
                if invoice is None:
                    continue
                verified_status = get_lifepay_transaction_status(invoice.order.coffee_shop, transaction_number)
                _apply_verified_lifepay_status(invoice, verified_status)
            except OrderTransitionError as exc:
                logger.info("LifePayCallbackView: %s transaction=%s", exc.code, transaction_number)
            except Exception:
                logger.exception("LifePayCallbackView: unexpected error transaction=%s", transaction_number)

        return Response({"success": True}, status=status.HTTP_200_OK)


# PaymentChangeStatus удалён (M0, P0): полностью неаутентифицированный (AllowAny)
# POST {"order_id": ...}, безусловно ставивший payment_status=PAID и
# status_orders=IN_PROGRESS для ЛЮБОГО заказа — фактически "бесплатно оплатить
# чей угодно заказ одним запросом без авторизации". Не используется мобильным
# приложением (grep по happy_island: 0 совпадений на "change-status"/
# "PaymentChangeStatus") и не имеет легитимного вызывающего кода в этом
# репозитории — удалён вместе с регистрацией в island_bali/urls.py, а не
# просто "исправлен", т.к. у endpoint нет ни одного корректного случая
# использования без полного redesign (см. финальный отчёт §C).


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_lifepay_status(request, order_id):
    """
    Опрос статуса счета LifePay напрямую через API LifePay и обновление БД.

    Контракт с мобильным приложением (SBPRepositoryImpl.getPaymentStatus /
    LifePayStatusResponse.fromJson) сохранён без изменений: тот же URL, тот
    же набор полей в ответе (order_id, payment_status, status_orders,
    lifepay_status, message).
    """
    try:
        order = Orders.objects.get(id=order_id, user=request.user)
    except Orders.DoesNotExist:
        return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    invoice = LifepayInvoice.objects.filter(order=order).order_by("-created_at").first()
    if not invoice:
        return Response({"error": "No LifePay invoice found for this order"}, status=status.HTTP_404_NOT_FOUND)

    verified_status = get_lifepay_transaction_status(order.coffee_shop, invoice.transaction_number)

    if verified_status.normalized_status == "NOT_FOUND":
        return Response({"error": verified_status.message or "Error from LifePay"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        _apply_verified_lifepay_status(invoice, verified_status)
    except OrderTransitionError as exc:
        logger.info("check_lifepay_status: %s order=%s", exc.code, order.id)

    order.refresh_from_db(fields=["payment_status", "status_orders"])

    return Response({
        "order_id": order.id,
        "payment_status": order.payment_status,
        "status_orders": order.status_orders,
        "lifepay_status": verified_status.raw_status_code,
        "message": verified_status.message,
    }, status=status.HTTP_200_OK)
