from django.contrib.auth.models import AnonymousUser
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from bonus_system.models import DiscountCard
from bonus_system.serializers import DiscountCardSerializer


@swagger_auto_schema(
    methods=['GET'],
    operation_description="Метод для получение QR code",
    responses={200: "OK", 400: "Bad Request"},
    tags=["Бонусная система"],
    operation_id="Получить QR-code",
    deprecated=True)
@api_view(["GET"])
def get_discount_card_from_user(request) -> Response:
    user = request.user
    discount_card = DiscountCard.objects.filter(user=user)
    serializer_class = DiscountCardSerializer(discount_card)
    if isinstance(user, AnonymousUser):
        return Response(
            {'error': 'Вы не авторизированны'},
            status=status.HTTP_400_BAD_REQUEST)
    if DiscountCard.objects.filter(user=user).exists():
        return Response(serializer_class)
    return Response(
        {'error': f'У пользователя {user} QR-CODE не найден'},
        status=status.HTTP_204_NO_CONTENT)
