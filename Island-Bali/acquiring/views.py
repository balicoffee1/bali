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