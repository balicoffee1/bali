import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from coffee_shop.models import CoffeeShop
from subtotal_api.connection_api import SubtotalClient


class GetDiscountForUser(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['shop_city', 'shop_street', 'phone_number'],
            properties={
                'shop_city': openapi.Schema(type=openapi.TYPE_STRING),
                'shop_street': openapi.Schema(type=openapi.TYPE_STRING),
                'phone_number': openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={
            status.HTTP_200_OK: openapi.Response(
                description="Скидка для пользователя",
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                    "discount": openapi.Schema(type=openapi.TYPE_INTEGER)})),
            status.HTTP_404_NOT_FOUND: openapi.Response(
                description="Скидка не найдена",
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                    "error": openapi.Schema(type=openapi.TYPE_STRING)})),
            status.HTTP_401_UNAUTHORIZED: openapi.Response(
                description="Не авторизован",
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                    "error": openapi.Schema(type=openapi.TYPE_STRING)})),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response(
                description="Внутренняя ошибка сервера",
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                    "error": openapi.Schema(type=openapi.TYPE_STRING)})),
        },
        operation_description="Получение скидки для пользователя.",
        operation_id="Получение скидки пользователя",
        tags=["CRM система"],
    )
    def post(self, request):
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')
        phone_number = request.data.get("phone_number")
        try:
            shop = CoffeeShop.objects.get(city__name=shop_city,
                                          street=shop_street)

            # TODO переделать, чтобы почта и пароль брались из кофейни
            try:
                client = SubtotalClient(email=shop.crm_system.login,
                                        password=shop.crm_system.password)
                if client.login():
                    discount_value = client.get_discount_for_phone_number(
                        phone_number)
                    if discount_value is not None:
                        return Response({"discount": discount_value})
                    else:
                        return Response({'error': 'No discount'},
                                        status=status.HTTP_404_NOT_FOUND)
                else:
                    return Response({'error': 'Not Authenticated'},
                                    status=status.HTTP_401_UNAUTHORIZED)
            except Exception as e:
                logging.error(f"An error occurred: {str(e)}")
                return Response({'error': 'Internal Server Error'},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            return Response(
                {
                    'error': 'Кафе не найдено, проверьте правильность '
                             'введеного города и улица на котором '
                             'находится кафе'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
