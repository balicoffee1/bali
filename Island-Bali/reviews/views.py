import logging

from django.db import transaction
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


from orders.models import Orders
from orders.services import OrderStateService

from .models import ReviewsCoffeeShop
from .serializers import ReviewsCoffeeShopSerializer
from .tasks import send_review_for_email, send_review_to_telegram

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
        serializer = ReviewsCoffeeShopSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        order = serializer.validated_data['orders']
        coffee_shop = serializer.validated_data['coffee_shop']
        if order.user_id != user.id:
            # Не раскрываем существование чужого заказа.
            return Response({"orders": ["Заказ не найден."]}, status=status.HTTP_404_NOT_FOUND)
        if coffee_shop.id != order.coffee_shop_id:
            return Response(
                {"coffee_shop": ["Кофейня не соответствует заказу."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.status_orders != Orders.COMPLETED:
            return Response(
                {"orders": ["Оценить можно только завершённый заказ."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        defaults = dict(serializer.validated_data)
        defaults.pop('orders')
        defaults['user'] = user

        # Повтор после сетевой неопределённости должен быть безопасным. Первый
        # запрос мог успеть сохранить отзыв, но потерять HTTP-ответ (как на M7).
        with transaction.atomic():
            review, created = ReviewsCoffeeShop.objects.get_or_create(
                orders=order,
                defaults=defaults,
            )
            OrderStateService.update_presentation(
                order.id, actor_type="customer", is_appreciated=True
            )

            if created:
                self._schedule_notifications(review)

        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(ReviewsCoffeeShopSerializer(review).data, status=response_status)

    @staticmethod
    def _schedule_notifications(review):
        """
        Внешние интеграции не выполняются Gunicorn-worker'ом: Telegram без
        timeout уже приводил к WORKER TIMEOUT и ложному 502 после сохранения
        отзыва. В Celery они могут повторяться независимо от HTTP-ответа.
        """
        def enqueue():
            try:
                if review.coffee_shop.telegram_id:
                    send_review_to_telegram.delay(review.id)
                if review.evaluation in (1, 2, 3):
                    send_review_for_email.delay(review.id)
            except Exception:
                # Сбой брокера не меняет результат уже сохранённой оценки.
                logger.exception("review_notification_enqueue_failed review=%s", review.id)

        transaction.on_commit(enqueue)
