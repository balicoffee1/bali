import logging

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

logger = logging.getLogger("reviews")

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
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        review = serializer.save(user=user)

        # Сначала доменный эффект: отзыв сохранён, значит заказ оценён. Раньше
        # это стояло ПОСЛЕ отправки уведомлений, и любая их ошибка означала,
        # что оценка есть, а is_appreciated не выставлен — то есть диалог
        # «оцените заказ» возвращался снова и снова.
        from orders.models import Orders
        from orders.services import OrderStateService

        order = Orders.objects.filter(
            id=serializer.validated_data.get('orders').id
        ).first()
        if order:
            OrderStateService.update_presentation(
                order.id, actor_type="customer", is_appreciated=True
            )

        self._notify(user, review, serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _notify(user, review, serializer):
        """
        Уведомления о новом отзыве — best effort.

        Раньше они выполнялись прямо в теле запроса и без обработки ошибок:
        send_review_to_user делает синхронный requests.get к api.telegram.org, а
        check_negative_feedback — отправку письма. Любая недоступность Telegram
        или SMTP превращалась в 500, и пользователь не мог оставить отзыв
        вообще. Мобильное приложение это раньше скрывало (диалог закрывался в
        finally независимо от результата), теперь оно честно показывает ошибку —
        и стало видно, что отправка отзыва падает.

        Отзыв уже сохранён и заказ уже помечен оценённым: сбой рассылки не
        должен ничего из этого отменять.
        """
        try:
            coffee_shop = serializer.validated_data.get('coffee_shop')
            review_text_admin = (
                f"Оценка: {review.evaluation}\n"
                f"Комментарий: {review.comments or 'Без комментариев'}"
            )
            send_review_to_user(
                chat_id=coffee_shop.telegram_id, review_text=review_text_admin
            )
        except Exception:
            logger.exception("review_telegram_notification_failed review=%s", review.id)

        try:
            check_negative_feedback(
                value=review.evaluation,
                review=serializer.data,
                email_coffeeshop=review.get_coffeeshop_email(),
                telegram_username=review.get_coffee_shop_telegram(),
            )
        except Exception:
            logger.exception("review_email_notification_failed review=%s", review.id)



def check_negative_feedback(value, review, email_coffeeshop,
                            telegram_username):
    """Выявляем является ли отзыв плохим"""
    if value in [1, 2, 3]:
        send_review_for_email(review, email_coffeeshop, telegram_username)
        