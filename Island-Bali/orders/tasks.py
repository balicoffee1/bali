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
from orders.state_machine import (
    BARISTA_CONFIRMATION_TIMEOUT_SECONDS,
    BARISTA_REMINDER_INTERVAL_SECONDS,
    PAYMENT_POLL_INTERVAL_SECONDS,
)

logger = logging.getLogger("orders.tasks")


def _get_baristas_for_shop(coffee_shop):
    """
    Находит сотрудников кофейни для отправки напоминаний.
    Сначала ищет смену со статусом 'Open'. Если таковых нет,
    возвращает всех зарегистрированных сотрудников кофейни.
    """
    if not coffee_shop:
        return []
    from staff.models import Shift, Staff

    active_shifts = Shift.objects.filter(
        staff__place_of_work=coffee_shop,
        status_shift="Open",
    ).select_related("staff__users")

    if active_shifts.exists():
        users = [shift.staff.users for shift in active_shifts if shift.staff and shift.staff.users]
        if users:
            return users

    staff_members = Staff.objects.filter(
        place_of_work=coffee_shop,
    ).select_related("users")
    return [s.users for s in staff_members if s.users]


def _format_barista_reminder(name: str, order_id: int, reminder_index: int) -> str:
    name_str = (name or "").strip() or "Бариста"
    messages = {
        1: f"{name_str}, прими заказ! Гости ждут вкусный кофе ☕️ Заказ №{order_id}",
        2: f"{name_str}, новый заказ №{order_id} скучает без тебя! Подтверди, пожалуйста ✨",
        3: f"{name_str}, у нас новый заказ №{order_id}! Давайте порадуем клиента 🚀",
        4: f"{name_str}, время на исходе! Заказ №{order_id} ждёт твоего подтверждения ⏳",
    }
    return messages.get(reminder_index, f"{name_str}, новый заказ №{order_id} ждёт подтверждения ⏳")


@shared_task
def send_barista_reminders_task(order_id, reminder_index=1):
    try:
        order = Orders.objects.select_related("coffee_shop").get(pk=order_id)
    except Orders.DoesNotExist:
        logger.warning("send_barista_reminders_task: order %s не найден", order_id)
        return

    # Напоминания актуальны ТОЛЬКО пока заказ в статусе NEW
    if order.status_orders != Orders.NEW:
        return

    from notifications.main import send_push_notification

    baristas = _get_baristas_for_shop(order.coffee_shop)
    for barista in baristas:
        name = getattr(barista, "first_name", None) or getattr(barista, "login", None) or "Бариста"
        body = _format_barista_reminder(name, order.id, reminder_index)
        send_push_notification(
            barista,
            "Новый заказ!",
            body,
            order_id=order.id,
            event="barista_new_order",
        )

    # Проверяем, нужно ли планировать следующее напоминание
    next_countdown = BARISTA_REMINDER_INTERVAL_SECONDS
    elapsed = reminder_index * BARISTA_REMINDER_INTERVAL_SECONDS
    if elapsed + next_countdown <= BARISTA_CONFIRMATION_TIMEOUT_SECONDS:
        send_barista_reminders_task.apply_async(
            args=[order_id, reminder_index + 1],
            countdown=next_countdown,
        )


@shared_task
def evaluate_barista_confirmation_deadline_task(order_id):
    try:
        OrderStateService.evaluate_barista_confirmation_deadline(order_id)
    except Orders.DoesNotExist:
        logger.warning("evaluate_barista_confirmation_deadline_task: order %s не найден", order_id)


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
