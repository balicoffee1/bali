from django.contrib.auth.models import AnonymousUser
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from bonus_system.models import DiscountCard
from bonus_system.serializers import DiscountCardSerializer

@swagger_auto_schema(
    methods=['GET'],
    operation_description="Метод для получения QR-кода",
    responses={200: "OK", 401: "Unauthorized", 204: "No Content"},
    tags=["Бонусная система"],
    operation_id="Получить QR-code",
    deprecated=True)
@api_view(["GET"])
def get_discount_card_from_user(request) -> Response:
    user = request.user
    if isinstance(user, AnonymousUser):
        return Response(
            {'error': 'Вы не авторизированы'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    discount_card = DiscountCard.objects.filter(user=user).first()
    if discount_card:
        serializer = DiscountCardSerializer(discount_card)
        return Response(serializer.data)
    return Response(
        {'error': f'У пользователя {user} QR-CODE не найден'},
        status=status.HTTP_204_NO_CONTENT
    )
