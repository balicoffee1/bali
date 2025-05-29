from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from .clients import AlphaBankClient, RussianStandard, TinkoffClient, RSBClient
from .serializers import PaymentRequestSerializer, PaymentResponseSerializer, RSBTransactionSerializer
from coffee_shop.models import CoffeeShop
from orders.models import Orders
import requests
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# Создание ссылки для оплаты через Russian Standard
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
    # @swagger_auto_schema(
    #     request_body=PaymentRequestSerializer,
    #     responses={200: openapi.Response('Успешная оплата', openapi.Schema(type=openapi.TYPE_OBJECT))},
    #     operation_description="Создание платежного заказа через SBP"
    # )
    def post(self, request, order_id, *args, **kwargs):
        

        try:
            order = Orders.objects.get(id=order_id)
            order.status_orders = Orders.IN_PROGRESS
            order.payment_status = Orders.PAID
            order.save()
            
        except requests.exceptions.HTTPError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

import requests
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import LifepayInvoice

LIFEPAY_API_URL = "https://api.life-pay.ru/v1/bill"
LIFEPAY_STATUS_URL = "https://api.life-pay.ru/v1/bill/status"

@api_view(['POST'])
def create_invoice(request):
    """
    Создание счета через LifePay и сохранение инвойса.
    """
    order_id = request.data.get('order_id')
    try:
        order = Orders.objects.get(id=order_id)
    except Orders.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)
    
    coffee_shop = order.coffee_shop

    data = {
        "apikey": coffee_shop.lifepay_api_key,
        "login": coffee_shop.lifepay_login,
        "amount": str(order.total_amount),
        "description": f"Оплата заказа #{order.id}",
        "customer_phone": order.customer_phone,
        "customer_email": order.customer_email,
        "method": "sbp",
        "callback_url": "http://79.174.81.151//api/lifepay/callback/"
    }

    response = requests.post(LIFEPAY_API_URL, json=data, verify=False)
    result = response.json()

    if result.get("code") == 0:
        invoice_data = result["data"]
        LifepayInvoice.objects.create(
            user=request.user,
            order=order,
            transaction_number=invoice_data["number"],
            payment_url=invoice_data["paymentUrl"],
            payment_url_web=invoice_data["paymentUrlWeb"]
        )
        order.status = 'pending'
        order.save()
        return Response({"payment_url": invoice_data["paymentUrlWeb"]})
    else:
        return Response({"error": result.get("message")}, status=400)


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def lifepay_callback(request):
    """
    Обработка callback от LifePay для обновления статуса заказа.
    """
    try:
        payload = request.data
        number = payload.get("number")
        status = payload.get("status")

        if not number or status is None:
            return JsonResponse({"error": "Invalid data"}, status=400)

        try:
            invoice = LifepayInvoice.objects.select_related('order').get(transaction_number=number)
        except LifepayInvoice.DoesNotExist:
            return JsonResponse({"error": "Invoice not found"}, status=404)

        order = invoice.order

        if status == 10:
            order.payment_status = Orders.PAID
            order.status_orders = Orders.IN_PROGRESS
        elif status in [20, 30]:
            order.status = 'cancelled'
        elif status == 15:
            order.status = 'pending'

        order.save()
        return JsonResponse({"message": "Status updated"})

    except Exception as e:
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
    Этот класс обрабатывает callback от LifePay.
    LifePay отправляет POST-запрос на наш callback_url
    с информацией о статусе транзакции.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        data = request.data.get("data", {})
        
        for transaction_number, info in data.items():
            status_code = info.get("status")
            invoice = LifepayInvoice.objects.filter(transaction_number=transaction_number)
            order = invoice.order if invoice else None
            if not order:
                continue

            if status_code == 10:
                order.payment_status = Orders.PAID
                order.status_orders = Orders.IN_PROGRESS  # Обновляем статус заказа
                order.save()

        return Response({"success": True}, status=status.HTTP_200_OK)


class PaymentChangeStatus(APIView):
    """
    Этот класс обрабатывает изменение статуса платежа.
    Он принимает POST-запрос с ID заказа и новым статусом.
    {
        "order_id": 123
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        order_id = request.data.get("order_id")

        try:
            order = Orders.objects.get(id=order_id)
            order.payment_status = Orders.PAID 
            order.status_orders = Orders.IN_PROGRESS  # Обновляем статус заказа
            order.save()
            return Response({"success": True}, status=status.HTTP_200_OK)
        except Orders.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)