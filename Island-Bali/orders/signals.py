"""
Django-сигналы orders (M1, п.24).

set_waiting_status_for_testing_order раньше форсировал status_orders/payment_status
на КАЖДЫЙ save() тестового заказа (в т.ч. невалидным значением payment_status="Waiting",
которого нет в Orders.PaymentStatus) — заново вызывался бы после каждого перехода через
OrderStateService, что при неудачном стечении обстоятельств создаёт петлю сигналов и
недетерминированное поведение. Теперь — один раз при создании, через сам сервис.

schedule_order_timeout остаётся сигналом, а не дублируется в двух местах создания заказа
(OrderViewSet.perform_create и CheckoutSerializer.create) — единственное, что он делает,
это устанавливает payment_deadline_at и планирует два timeout task'а; он НЕ трогает
status_orders/payment_status и поэтому не подпадает под "запрет на прямую мутацию status".
"""
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

from .models import Orders
from .state_machine import (
    BARISTA_CONFIRMATION_TIMEOUT_SECONDS,
    BARISTA_REMINDER_INTERVAL_SECONDS,
)
from .tasks import (
    evaluate_barista_confirmation_deadline_task,
    send_barista_reminders_task,
)

logger = logging.getLogger("orders.signals")


@receiver(post_save, sender=Orders)
def set_waiting_status_for_testing_order(sender, instance, created, **kwargs):
    if not created or not instance.is_testing:
        return
    from .services import OrderStateService

    try:
        OrderStateService.accept(instance.id, staff_user=None)
    except Exception:  # pragma: no cover - тестовый заказ не должен ронять запрос создания
        logger.exception("Не удалось перевести тестовый заказ %s в Waiting", instance.id)


@receiver(post_save, sender=Orders)
def initialize_barista_confirmation_sla(sender, instance, created, **kwargs):
    if not created:
        return

    order_id = instance.id

    def _schedule():
        # Внутри on_commit: диспетчеризация Celery-тасков не должна происходить,
        # если внешняя транзакция (создание заказа) в итоге откатится.
        send_barista_reminders_task.apply_async(
            args=[order_id, 1], countdown=BARISTA_REMINDER_INTERVAL_SECONDS
        )
        evaluate_barista_confirmation_deadline_task.apply_async(
            args=[order_id], countdown=BARISTA_CONFIRMATION_TIMEOUT_SECONDS
        )

    transaction.on_commit(_schedule)
