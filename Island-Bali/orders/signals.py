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
from .state_machine import PAYMENT_WINDOW_SECONDS
from .tasks import evaluate_payment_deadline_task, finalize_payment_window_task

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
def initialize_payment_window(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.payment_deadline_at is None:
        deadline = timezone.now() + timedelta(seconds=PAYMENT_WINDOW_SECONDS)
        Orders.objects.filter(pk=instance.pk).update(payment_deadline_at=deadline)
        instance.payment_deadline_at = deadline

    order_id = instance.id

    def _schedule():
        # Внутри on_commit: диспетчеризация Celery-тасков не должна происходить,
        # если внешняя транзакция (создание заказа) в итоге откатится — иначе
        # таймаут-таск может стартовать раньше, чем строка Orders вообще
        # закоммичена, и упасть на Orders.DoesNotExist, либо (хуже) отработать
        # против несуществующего/чужого заказа при переиспользовании PK.
        evaluate_payment_deadline_task.apply_async(args=[order_id], countdown=PAYMENT_WINDOW_SECONDS)
        finalize_payment_window_task.apply_async(args=[order_id], countdown=PAYMENT_WINDOW_SECONDS + 30)

    transaction.on_commit(_schedule)
