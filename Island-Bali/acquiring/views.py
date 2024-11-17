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


rus_standard = RussianStandard()

@swagger_auto_schema(
    request_body=PaymentRequestSerializer,
    operation_description="Этот запрос создаёт по переданным параметрам оплаты счёт и генерирует для отображения в виде предварительного просмотра html-код письма счёта.",
    responses={200: PaymentResponseSerializer, 400: "Bad Request"},
    tags=["Эквайринг"],
    operation_id="Создание ссылки для оплаты",
    methods=['POST']) 
@api_view(['POST'])
def get_link(request):
    """
    Этот запрос создаёт по переданным параметрам оплаты счёт и генерирует
    для отображения в виде предварительного просмотра html-код письма счёта.
    В ответ на данный запрос возвращается объект с полями invoice_id,
    invoice_url, и invoice.
    """
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
def get_status_payment(request, invoice_id):
    check_status = rus_standard.check_order(invoice_id)
    return Response(data={"status": check_status})





class AlphaCreatePaymentOrderView(APIView):
    def post(self, request, *args, **kwargs):
        client = AlphaBankClient()
        payment_data = request.data

        try:
            response = client.create_payment_order(payment_data)
            return Response(response, status=status.HTTP_201_CREATED)
        except requests.exceptions.HTTPError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class AlphaGetPaymentStatusView(APIView):
    def get(self, request, external_id, *args, **kwargs):
        client = AlphaBankClient()

        try:
            status_response = client.get_payment_status(external_id)
            return Response(status_response, status=status.HTTP_200_OK)
        except requests.exceptions.HTTPError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)



class TBCreateOrderView(APIView):
    def post(self, request, *args, **kwargs):
        client = TinkoffClient()
        order_data = request.data

        try:
            response = client.create_order(order_data)
            return Response(response, status=status.HTTP_201_CREATED)
        except requests.exceptions.HTTPError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class TBGetOrderView(APIView):
    def get(self, request, order_id, *args, **kwargs):
        client = TinkoffClient()

        try:
            order = client.get_order(order_id)
            return Response(order, status=status.HTTP_200_OK)
        except requests.exceptions.HTTPError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)



from django.http import JsonResponse
from .utils import RSBClient
import requests

@api_view(["POST"])
def rsb_transaction(request):
    if request.method == "POST":
        rsb_client = RSBClient()

        command = "v"  
        amount = "123"
        currency = "643"
        description = "Test transaction"

        response = rsb_client.send_request(command, amount, currency, description=description)

        if response["success"]:
            return JsonResponse({"status": "success", "data": response["data"]})
        else:
            return JsonResponse({"status": "error", "message": response["error"]})
