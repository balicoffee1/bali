"""
Детерминированный timeout заказа (M1, п.13-14).

Раньше — один Celery task "sleep 90s -> if payment != PAID: cancel()", без учёта того,
что платёжная попытка могла быть начата вовремя и просто ещё не подтверждена провайдером.
Теперь — две задачи:

  evaluate_payment_deadline_task  — T0 + 90s (payment_deadline_at)
  finalize_payment_window_task    — T0 + 120s (payment_deadline_at + grace)

Обе — тонкие обёртки над orders.services.OrderStateService, которому передаётся реальная
проверка статуса LifePay. Сама бизнес-логика (что делать при PAID/PENDING/FAILED) живёт
в сервисе и покрыта тестами независимо от Celery/LifePay (там provider_status_checker
подменяется моком).
"""
import logging

from celery import shared_task

from acquiring.providers import ProviderPaymentStatus, get_latest_invoice, get_lifepay_transaction_status
from orders.models import Orders
from orders.services import OrderStateService
from orders.state_machine import PAYMENT_POLL_INTERVAL_SECONDS

logger = logging.getLogger("orders.tasks")


def _lifepay_status_checker(order) -> ProviderPaymentStatus:
    invoice = get_latest_invoice(order)
    if invoice is None:
        return ProviderPaymentStatus(normalized_status="NOT_FOUND", message="no_invoice")
    return get_lifepay_transaction_status(order.coffee_shop, invoice.transaction_number)


@shared_task
def evaluate_payment_deadline_task(order_id):
    try:
        OrderStateService.evaluate_payment_deadline(order_id, provider_status_checker=_lifepay_status_checker)
    except Orders.DoesNotExist:
        logger.warning("evaluate_payment_deadline_task: order %s не найден", order_id)


@shared_task
def poll_payment_status_task(order_id):
    """
    Серверный опрос провайдера, пока идёт оплата (M7, шаг 4).

    Самопланирующаяся цепочка вместо periodic beat-задачи: опрашивать нужно только
    те заказы, где оплата реально начата, и только внутри их окна — beat пришлось бы
    каждые несколько секунд сканировать всю таблицу. Цепочка гарантированно
    завершается: sync_payment_from_provider возвращает False, как только оплата
    решена или окно закрылось.
    """
    try:
        should_continue = OrderStateService.sync_payment_from_provider(
            order_id, provider_status_checker=_lifepay_status_checker
        )
    except Orders.DoesNotExist:
        logger.warning("poll_payment_status_task: order %s не найден", order_id)
        return

    if should_continue:
        poll_payment_status_task.apply_async(
            args=[order_id], countdown=PAYMENT_POLL_INTERVAL_SECONDS
        )


@shared_task
def finalize_payment_window_task(order_id):
    try:
        OrderStateService.finalize_payment_window(order_id, provider_status_checker=_lifepay_status_checker)
    except Orders.DoesNotExist:
        logger.warning("finalize_payment_window_task: order %s не найден", order_id)
