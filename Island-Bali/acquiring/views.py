from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
import requests
from .alpha_client import AlphaBankClient
from acquiring.utils import RussianStandard
from .serializers import PaymentRequestSerializer, PaymentResponseSerializer
from .tinkoff_client import TinkoffClient
from coffee_shop.models import CoffeeShop


@swagger_auto_schema(
    request_body=PaymentRequestSerializer,
    operation_description="Этот запрос создаёт по переданным параметрам оплаты счёт и генерирует для отображения в виде предварительного просмотра html-код письма счёта.",
    responses={200: PaymentResponseSerializer, 400: "Bad Request"},
    tags=["Эквайринг"],
    operation_id="Создание ссылки для оплаты",
    methods=['POST']) 
@api_view(['POST'])
def get_link(request, coffee_shop_id):
    """
    Создание ссылки для оплаты через Russian Standard.
    """
    coffee_shop = CoffeeShop.objects.get(id=coffee_shop_id)
    rus_standard = RussianStandard(
        user=coffee_shop.bank_user,
        password=coffee_shop.bank_password
    )

    serializer = PaymentRequestSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        payment = rus_standard.link_for_payment(
            pay_amount=data['pay_amount'],
            client_id=data['client_id'],
            order_id=data['order_id'],
            client_email=data['client_email'],
            service_name=data['service_name'],
            client_phone=data['client_phone']
        )
        response_serializer = PaymentResponseSerializer(payment)
        return Response(data=response_serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    operation_description="Метод `get_status_payment` используется для проверки статуса оплаты.",
    responses={200: "OK", 400: "Bad Request"},
    tags=["Эквайринг"],
    operation_id="Проверка статуса заказа",
    methods=['GET'])
@api_view(['GET'])
def get_status_payment(request, coffee_shop_id, invoice_id):
    coffee_shop = CoffeeShop.objects.get(id=coffee_shop_id)
    rus_standard = RussianStandard(
        user=coffee_shop.bank_user,
        password=coffee_shop.bank_password
    )

    check_status = rus_standard.check_order(invoice_id)
    return Response(data={"status": check_status})


class AlphaCreatePaymentOrderView(APIView):
    def post(self, request, coffee_shop_id, *args, **kwargs):
        coffee_shop = CoffeeShop.objects.get(id=coffee_shop_id)
        client = AlphaBankClient(api_token=coffee_shop.bank_api_token)
        payment_data = request.data

        try:
            response = client.create_payment_order(payment_data)
            return Response(response, status=status.HTTP_201_CREATED)
        except requests.exceptions.HTTPError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class AlphaGetPaymentStatusView(APIView):
    def get(self, request, coffee_shop_id, external_id, *args, **kwargs):
        coffee_shop = CoffeeShop.objects.get(id=coffee_shop_id)
        client = AlphaBankClient(api_token=coffee_shop.bank_api_token)

        try:
            status_response = client.get_payment_status(external_id)
            return Response(status_response, status=status.HTTP_200_OK)
        except requests.exceptions.HTTPError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TBCreateOrderView(APIView):
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

class TBGetOrderView(APIView):
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



from django.http import JsonResponse
from .utils import RSBClient
import requests
from .serializers import RSBTransactionSerializer

class RSBTransactionView(APIView):
    @swagger_auto_schema(
        request_body=RSBTransactionSerializer,
        responses={200: RSBTransactionSerializer, 400: "Bad Request"},
        tags=["Эквайринг"]
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
