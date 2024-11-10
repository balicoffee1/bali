from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ReviewsCoffeeShopSerializer
from .tasks import send_review_for_email
from .telegram_bot import send_review_to_user  # Импорт функции отправки

TAGS_REVIEWS = ['Оставить отзыв']

class CreateReviewAPIView(APIView):
    """Создание отзыва"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=ReviewsCoffeeShopSerializer,
        operation_description="Создание отзыва к кофейне",
        tags=TAGS_REVIEWS,
        operation_id="Оставить отзыв",
        responses={
            201: openapi.Response(description="Отзыв успешно создан",
                                  schema=ReviewsCoffeeShopSerializer),
            400: "Некорректный запрос"
        }
    )
    def post(self, request: Request, *args, **kwargs):
        user = request.user
        data_with_user = request.data.copy()
        data_with_user["user"] = user.id
        serializer = ReviewsCoffeeShopSerializer(data=data_with_user)
        if serializer.is_valid():
            review = serializer.save(user=user)
            id_coffeshop = serializer.validated_data.get('id')
            # Отправляем отзыв в Telegram, если есть chat_id
            if hasattr(user, 'telegram_chat_id') and user.telegram_chat_id:
                review_text = (
                    f"Спасибо за ваш отзыв!\n"
                    f"Оценка: {review.evaluation}\n"
                    f"Комментарий: {review.comments or 'Без комментариев'}"
                )
                send_review_to_user(..., review_text)

            email_coffeeshop = review.get_coffeeshop_email()
            telegram_contact = review.get_coffee_shop_telegram()
            check_negative_feedback(value=review.evaluation,
                                    review=serializer.data,
                                    email_coffeeshop=email_coffeeshop,
                                    telegram_username=telegram_contact)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



def check_negative_feedback(value, review, email_coffeeshop,
                            telegram_username):
    """Выявляем является ли отзыв плохим"""
    if value in [1, 2, 3]:
        send_review_for_email(review, email_coffeeshop, telegram_username)
        