"""
OrderStateService — единственная точка мутации status_orders/payment_status (M1).

Инвариант: ни один HTTP endpoint, Celery task, payment callback, admin endpoint,
staff endpoint или Django signal не меняет order.status_orders / order.payment_status
самостоятельно. Всё проходит через методы этого класса.

Каждый метод:
  * оборачивает чтение+изменение в transaction.atomic() + select_for_update()
    (конкурентная защита — конкурирующий запрос ждёт лока, а не читает устаревшую строку);
  * проверяет текущее состояние ПОСЛЕ получения лока (а не до входа в транзакцию);
  * либо применяет допустимый переход, либо поднимает OrderTransitionError, либо
    (для повторных идемпотентных вызовов — двойной "Принять"/"Готово") молча
    возвращает заказ без изменений;
  * при реальном изменении увеличивает order.version и логирует переход (без PII)
    через transaction.on_commit — то есть только про подтверждённые изменения.
"""
from __future__ import annotations

from datetime import timedelta
import logging

from django.db import transaction
from django.utils import timezone

from .models import OrderDialogAck, Orders, PaymentReconciliation, PaymentWebhookEvent
from .realtime import publish_order_status_changed, snapshot_from_order
from .state_machine import (
    GRACE_PERIOD_SECONDS,
    ORDER_TERMINAL_STATUSES,
    PAYMENT_POLL_INTERVAL_SECONDS,
    PAYMENT_WINDOW_SECONDS,
    TIME_CHANGE_CONFIRMATION_TIMEOUT_SECONDS,
    OrderTransitionError,
    is_order_transition_allowed,
)

logger = logging.getLogger("orders.state")


# Presentation-поля, которые видит клиент, но которые не входят ни в одну state
# machine: их меняет персонал/клиент, version при этом не растёт, а событие
# отправить всё равно обязаны. updated_time намеренно отсутствует: изменение
# времени — версионируемая бизнес-операция propose_time_change().
PRESENTATION_FIELDS = frozenset({
    "cancellation_reason", "staff_comments", "client_comments", "time_is_finish",
    "is_appreciated",
})


def _save_and_publish(order, update_fields):
    """
    Единственный способ опубликовать realtime-событие (M7).

    Инкремент event_seq и сохранение изменения происходят одной строкой в одной
    транзакции, поэтому «событие опубликовано, но event_seq не вырос» и обратное
    невозможны по построению. Снапшот строится здесь же (внутри atomic, пока order
    залочен и уже сохранён), публикация — только после реального commit (M3, п.27, п.40).
    """
    order.event_seq += 1
    fields = list(update_fields)
    for required in ("event_seq", "updated_at"):
        if required not in fields:
            fields.append(required)
    order.save(update_fields=fields)
    snapshot = snapshot_from_order(order)
    transaction.on_commit(lambda: publish_order_status_changed(snapshot))


def _schedule_payment_poll(order_id):
    """Импорт задачи локальный: orders.tasks импортирует этот модуль на уровне модуля."""

    def _schedule():
        from .tasks import poll_payment_status_task

        poll_payment_status_task.apply_async(args=[order_id], countdown=PAYMENT_POLL_INTERVAL_SECONDS)

    transaction.on_commit(_schedule)


def _notify_customer(order_id, title, body_builder, *, event):
    """Best-effort customer push; a broker/FCM outage must not fail the API.

    body_builder — callable(order) -> str, а не готовая строка: заказ всё равно
    перечитывается здесь (уже после commit), и текст вроде причины отмены должен
    браться из зафиксированного состояния, а не из объекта в памяти вызывающего.
    """
    try:
        from notifications.main import send_push_notification

        order = Orders.objects.select_related("user").get(pk=order_id)
        send_push_notification(
            order.user,
            title,
            body_builder(order),
            order_id=order.id,
            event=event,
        )
    except Exception:
        logger.exception(
            "customer_notification_failed order_id=%s event=%s", order_id, event
        )


def _schedule_in_progress_notification(order):
    transaction.on_commit(
        lambda order_id=order.id: _notify_customer(
            order_id,
            "Заказ готовится",
            lambda order: f"Заказ №{order.id} принят в работу",
            event="order_in_progress",
        )
    )


def _schedule_cancel_notification(order, *, actor_type):
    """Пуш об отмене.

    Отмену, инициированную самим клиентом, не анонсируем: он только что нажал
    кнопку и уже видит результат. Системная автоотмена по истечении окна оплаты,
    наоборот, — единственный случай, когда клиент вообще ничего не узнает:
    приложение к этому моменту обычно закрыто, а ручки staff/admin, которые
    раньше были единственными источниками пуша об отмене, здесь не участвуют.
    """
    if actor_type == "customer":
        return

    if actor_type == "system":
        def body(order):
            return f"Заказ №{order.id} отменён: оплата не поступила"
    else:
        def body(order):
            reason = (order.cancellation_reason or "").strip()
            return (
                f"Заказ №{order.id} отменён: {reason}"
                if reason
                else f"Заказ №{order.id} отменён"
            )

    transaction.on_commit(
        lambda order_id=order.id: _notify_customer(
            order_id, "Заказ отменён", body, event="order_canceled"
        )
    )


ADMIN_STATUS_MESSAGES = {
    Orders.WAITING: (
        "Статус заказа изменён",
        lambda order: f"Заказ №{order.id} переведён в ожидание",
    ),
    Orders.IN_PROGRESS: (
        "Заказ готовится",
        lambda order: f"Заказ №{order.id} принят в работу",
    ),
    Orders.COMPLETED: (
        "Заказ готов",
        lambda order: f"Заказ №{order.id} готов к выдаче",
    ),
}


def _schedule_admin_status_notification(order, new_status):
    """Пуш при ручной смене статуса админом.

    Отмену отдаём общему пути (_schedule_cancel_notification), чтобы текст с
    причиной был один и тот же, кто бы отмену ни инициировал.
    """
    if new_status == Orders.CANCELED:
        _schedule_cancel_notification(order, actor_type="admin")
        return

    message = ADMIN_STATUS_MESSAGES.get(new_status)
    if message is None:
        return

    title, body_builder = message
    transaction.on_commit(
        lambda order_id=order.id: _notify_customer(
            order_id, title, body_builder, event="order_status_changed"
        )
    )


def _resolve_staff(user, coffee_shop_id):
    """
    accept()/complete() получают staff_user из request.user (CustomUser) — так их
    вызывают orders/views.py и staff/views.py, всегда после is_staff_for_order()
    (staff/utils.py), которая уже подтвердила, что для этого пользователя есть
    Staff-запись в кофейне заказа. Orders.staff, однако, FK на Staff, а не на
    CustomUser — прямое присваивание CustomUser в это поле падает с ValueError.
    Резолвим реальную Staff-запись здесь; None (тестовые/system-заказы) остаётся None.
    """
    if user is None:
        return None
    from staff.models import Staff

    return Staff.objects.filter(users=user, place_of_work_id=coffee_shop_id).first()


def _log_transition(order, *, operation, actor_type, prev_order_status, prev_payment_status, extra=None):
    """Структурированный лог перехода. Никогда не включает телефон/email/JWT/данные карты."""
    payload = {
        "order_id": order.id,
        "previous_order_status": prev_order_status,
        "new_order_status": order.status_orders,
        "previous_payment_status": prev_payment_status,
        "new_payment_status": order.payment_status,
        "actor_type": actor_type,
        "operation": operation,
        "version": order.version,
    }
    if extra:
        payload.update(extra)
    logger.info("order_transition %s", payload)


class OrderStateService:
    """Публичное API — именованные бизнес-операции, а не универсальный transition(event)."""

    # ------------------------------------------------------------------ order lifecycle

    @staticmethod
    def attach_receipt(order_id, *, receipt_file, actor_type):
        """Attach the fiscal receipt and publish the updated order to both audiences."""
        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)
            order.receipt_photo = receipt_file
            order.issued = True
            order.checkLoaded = True
            _save_and_publish(order, ["receipt_photo", "issued", "checkLoaded"])

        transaction.on_commit(
            lambda: _log_transition(
                order,
                operation="attach_receipt",
                actor_type=actor_type,
                prev_order_status=order.status_orders,
                prev_payment_status=order.payment_status,
            )
        )
        return order

    @staticmethod
    def accept(order_id, *, staff_user):
        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)
            prev_order_status, prev_payment_status = order.status_orders, order.payment_status

            if order.status_orders == Orders.WAITING:
                return order  # повторный тап "Принять" — безопасный no-op

            if not is_order_transition_allowed(order.status_orders, Orders.WAITING):
                raise OrderTransitionError(
                    "invalid_transition",
                    f"Нельзя принять заказ в статусе {order.status_orders}.",
                    order,
                )

            order.status_orders = Orders.WAITING
            order.staff = _resolve_staff(staff_user, order.coffee_shop_id)
            order.payment_deadline_at = timezone.now() + timedelta(seconds=PAYMENT_WINDOW_SECONDS)
            order.version += 1
            _save_and_publish(order, ["status_orders", "staff", "payment_deadline_at", "version"])

            def _schedule_tasks_and_push(target_order_id):
                from .tasks import evaluate_payment_deadline_task, finalize_payment_window_task

                evaluate_payment_deadline_task.apply_async(args=[target_order_id], countdown=PAYMENT_WINDOW_SECONDS)
                finalize_payment_window_task.apply_async(
                    args=[target_order_id], countdown=PAYMENT_WINDOW_SECONDS + GRACE_PERIOD_SECONDS
                )
                _notify_customer(
                    target_order_id,
                    "Заказ подтверждён",
                    lambda order: f"Заказ №{order.id} принят! Оплатите в течение 2 минут ☕️",
                    event="order_accepted",
                )

            transaction.on_commit(lambda order_id=order.id: _schedule_tasks_and_push(order_id))

        transaction.on_commit(
            lambda: _log_transition(
                order, operation="accept", actor_type="staff",
                prev_order_status=prev_order_status, prev_payment_status=prev_payment_status,
            )
        )
        return order

    @staticmethod
    def propose_time_change(order_id, *, staff_user, updated_time, reason=None):
        """Принять заказ при необходимости и запросить согласие на новое время.

        Пока предложение ожидает решения, первоначальный SLA бариста уже снят:
        NEW переводится в WAITING в той же транзакции. Оплата блокируется до
        подтверждения конкретной ревизии клиентом.
        """
        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)
            prev_order_status, prev_payment_status = order.status_orders, order.payment_status

            if order.status_orders not in (Orders.NEW, Orders.WAITING):
                raise OrderTransitionError(
                    "invalid_time_change_state",
                    "Менять время можно только у нового или ожидающего заказа.",
                    order,
                )
            if order.payment_status != Orders.NEW or order.payment_started_at is not None:
                raise OrderTransitionError(
                    "payment_already_started",
                    "Нельзя менять время после начала оплаты.",
                    order,
                )

            now = timezone.now()
            changed_fields = [
                "updated_time", "client_confirmed", "time_change_revision",
                "pending_time_change_revision", "time_change_confirmation_deadline_at",
                "payment_deadline_at",
            ]
            order.updated_time = updated_time
            if reason is not None:
                order.cancellation_reason = reason
                changed_fields.append("cancellation_reason")
            order.client_confirmed = False
            order.time_change_revision += 1
            order.pending_time_change_revision = order.time_change_revision
            order.time_change_confirmation_deadline_at = now + timedelta(
                seconds=TIME_CHANGE_CONFIRMATION_TIMEOUT_SECONDS
            )
            # Если заказ уже был принят обычной кнопкой, гасим его прежнее окно
            # оплаты. Отложенные payment-задачи увидят pending-ревизию и выйдут.
            order.payment_deadline_at = None

            if order.status_orders == Orders.NEW:
                order.status_orders = Orders.WAITING
                order.staff = _resolve_staff(staff_user, order.coffee_shop_id)
                changed_fields.extend(["status_orders", "staff"])

            order.version += 1
            changed_fields.append("version")
            _save_and_publish(order, changed_fields)

            def _schedule_confirmation(target_order_id):
                from .tasks import evaluate_time_change_confirmation_deadline_task

                evaluate_time_change_confirmation_deadline_task.apply_async(
                    args=[target_order_id], countdown=TIME_CHANGE_CONFIRMATION_TIMEOUT_SECONDS,
                )
                _notify_customer(
                    target_order_id,
                    "Подтвердите новое время",
                    lambda current: (
                        f"Бариста предложил новое время для заказа №{current.id}. "
                        "Подтвердите его в приложении в течение 5 минут."
                    ),
                    event="time_change_requested",
                )

            transaction.on_commit(lambda order_id=order.id: _schedule_confirmation(order_id))

        transaction.on_commit(
            lambda: _log_transition(
                order,
                operation="propose_time_change",
                actor_type="staff",
                prev_order_status=prev_order_status,
                prev_payment_status=prev_payment_status,
                extra={"time_change_revision": order.time_change_revision},
            )
        )
        return order

    @staticmethod
    def cancel(order_id, *, actor_type, reason=""):
        """actor_type: 'customer' | 'staff' | 'system' (Celery timeout)."""
        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)
            prev_order_status, prev_payment_status = order.status_orders, order.payment_status

            if order.status_orders == Orders.CANCELED:
                return order  # повторная отмена — безопасный no-op

            if order.status_orders in ORDER_TERMINAL_STATUSES:
                raise OrderTransitionError(
                    "invalid_transition",
                    f"Нельзя отменить заказ в статусе {order.status_orders}.",
                    order,
                )

            # Инвариант M1 п.15: уже зафиксированный PAID запрещает автоотмену системой.
            if actor_type == "system" and order.payment_status == Orders.PAID:
                return order

            order.status_orders = Orders.CANCELED
            order.cancellation_reason = reason
            # Показан ли клиенту диалог отмены — вопрос не сервиса: это
            # OrderDialogAck, который пишет само приложение после показа.
            order.version += 1
            _save_and_publish(order, ["status_orders", "cancellation_reason", "version"])
            _schedule_cancel_notification(order, actor_type=actor_type)

        transaction.on_commit(
            lambda: _log_transition(
                order, operation="cancel", actor_type=actor_type,
                prev_order_status=prev_order_status, prev_payment_status=prev_payment_status,
                extra={"reason_present": bool(reason)},
            )
        )
        return order

    @staticmethod
    def complete(order_id, *, staff_user):
        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)
            prev_order_status, prev_payment_status = order.status_orders, order.payment_status

            if order.status_orders == Orders.COMPLETED:
                return order  # повторный тап "Готово" — безопасный no-op

            if not is_order_transition_allowed(order.status_orders, Orders.COMPLETED):
                raise OrderTransitionError(
                    "invalid_transition",
                    f"Нельзя завершить заказ в статусе {order.status_orders} (требуется In Progress).",
                    order,
                )

            order.status_orders = Orders.COMPLETED
            if staff_user is not None:
                order.staff = _resolve_staff(staff_user, order.coffee_shop_id)
            order.version += 1
            _save_and_publish(order, ["status_orders", "staff", "version"])
            transaction.on_commit(
                lambda order_id=order.id: _notify_customer(
                    order_id,
                    "Заказ готов",
                    lambda order: f"Заказ №{order.id} готов к выдаче",
                    event="order_completed",
                )
            )

            if order.cart_id:
                order.cart.is_active = False
                order.cart.save(update_fields=["is_active"])

        transaction.on_commit(
            lambda: _log_transition(
                order, operation="complete", actor_type="staff",
                prev_order_status=prev_order_status, prev_payment_status=prev_payment_status,
            )
        )
        return order

    @staticmethod
    def client_confirmed(order_id, *, user, time_change_revision):
        """Подтвердить конкретную ожидающую ревизию нового времени."""
        expired = False
        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)
            if order.user_id != user.id:
                raise OrderTransitionError("forbidden", "Заказ принадлежит другому пользователю.", order)
            if order.status_orders in ORDER_TERMINAL_STATUSES:
                raise OrderTransitionError("order_closed", "Заказ уже закрыт.", order)
            if (
                order.pending_time_change_revision is None
                and order.client_confirmed
                and time_change_revision == order.time_change_revision
            ):
                return order  # безопасный ретрай подтверждения той же ревизии
            if order.pending_time_change_revision is None:
                raise OrderTransitionError(
                    "no_pending_time_change", "Нет изменения времени, ожидающего подтверждения.", order
                )
            if time_change_revision != order.pending_time_change_revision:
                raise OrderTransitionError(
                    "stale_time_change",
                    "Это устаревшее предложение времени. Откройте актуальное.", order
                )
            if (
                order.time_change_confirmation_deadline_at is not None
                and timezone.now() > order.time_change_confirmation_deadline_at
            ):
                # Отменяем уже ПОСЛЕ выхода из этого atomic: исключение внутри
                # блока откатило бы и саму отмену.
                expired = True
            else:
                prev_order_status, prev_payment_status = order.status_orders, order.payment_status
                order.client_confirmed = True
                order.time_is_finish = order.updated_time
                order.pending_time_change_revision = None
                order.time_change_confirmation_deadline_at = None
                order.payment_deadline_at = timezone.now() + timedelta(seconds=PAYMENT_WINDOW_SECONDS)
                order.version += 1
                _save_and_publish(order, [
                    "client_confirmed", "time_is_finish", "pending_time_change_revision",
                    "time_change_confirmation_deadline_at", "payment_deadline_at", "version",
                ])

                def _schedule_payment_and_push(target_order_id):
                    from .tasks import evaluate_payment_deadline_task, finalize_payment_window_task

                    evaluate_payment_deadline_task.apply_async(
                        args=[target_order_id], countdown=PAYMENT_WINDOW_SECONDS
                    )
                    finalize_payment_window_task.apply_async(
                        args=[target_order_id],
                        countdown=PAYMENT_WINDOW_SECONDS + GRACE_PERIOD_SECONDS,
                    )
                    _notify_customer(
                        target_order_id,
                        "Новое время подтверждено",
                        lambda current: f"Заказ №{current.id} подтверждён. Оплатите в течение 2 минут ☕️",
                        event="time_change_confirmed",
                    )

                transaction.on_commit(lambda order_id=order.id: _schedule_payment_and_push(order_id))

        if expired:
            OrderStateService.cancel(
                order.id,
                actor_type="system",
                reason="Время подтверждения нового времени заказа истекло. Заказ отменён.",
            )
            raise OrderTransitionError(
                "time_change_expired", "Время подтверждения нового времени истекло.", order
            )

        transaction.on_commit(
            lambda: _log_transition(
                order, operation="client_confirmed", actor_type="customer",
                prev_order_status=prev_order_status, prev_payment_status=prev_payment_status,
            )
        )
        return order

    @staticmethod
    def evaluate_time_change_confirmation_deadline(order_id):
        """Отменить заказ, если клиент не ответил на актуальную ревизию времени."""
        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)
            if (
                order.status_orders in ORDER_TERMINAL_STATUSES
                or order.pending_time_change_revision is None
            ):
                return order
            deadline = order.time_change_confirmation_deadline_at
            if deadline is not None and timezone.now() < deadline:
                return order
            return OrderStateService.cancel(
                order.id,
                actor_type="system",
                reason="Клиент не подтвердил новое время заказа. Заказ отменён.",
            )

    @staticmethod
    def order_created(order_id):
        """
        Публикация события о только что созданном заказе (M7).

        Создание — не переход state machine, version остаётся 0. Но клиенту событие
        нужно: диалог «ожидание подтверждения бариста» открывается по факту появления
        заказа в статусе New, и без этого события он после отказа от polling'а не
        откроется вовсе (а на втором устройстве не откроется и подавно).
        """
        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)
            _save_and_publish(order, [])
        return order

    @staticmethod
    def update_presentation(order_id, *, actor_type, **fields):
        """
        Изменение presentation-полей заказа (M7): причина/комментарии и UI-поля.

        Это не переход state machine — version не растёт, допустимость перехода не
        проверяется. Но событие публикуется обязательно: после отказа от polling'а
        клиент иначе не узнает об изменении вообще. Изменение времени идёт через
        propose_time_change(), чтобы согласие было привязано к ревизии.

        Неизвестные поля отвергаются, а не игнорируются молча: PRESENTATION_FIELDS —
        это ещё и граница, через которую status_orders/payment_status/version не
        протащить mass-assignment'ом.
        """
        unknown = set(fields) - PRESENTATION_FIELDS
        if unknown:
            raise OrderTransitionError(
                "invalid_presentation_field",
                f"Недопустимые для presentation-обновления поля: {sorted(unknown)}",
            )
        if not fields:
            return Orders.objects.get(pk=order_id)

        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)
            changed = [name for name, value in fields.items() if getattr(order, name) != value]
            if not changed:
                return order  # идемпотентно: нечего менять — нечего и публиковать
            for name in changed:
                setattr(order, name, fields[name])
            _save_and_publish(order, changed)

        transaction.on_commit(
            lambda: logger.info(
                "order_presentation_updated %s",
                {"order_id": order.id, "actor_type": actor_type,
                 "fields": sorted(changed), "event_seq": order.event_seq},
            )
        )
        return order

    @staticmethod
    def acknowledge_dialog(order_id, *, user, dialog_key):
        """
        Клиент закрыл диалог — записываем это навсегда (M7, часть B).

        Идемпотентно по построению (unique_together): повторный ack — не ошибка и не
        гонка, а no-op без события. Событие публикуется только на первый ack и нужно
        ровно для одного сценария — второе устройство того же пользователя, где
        диалог висит открытым, должно его закрыть.

        version не трогаем: подтверждение диалога не меняет бизнес-состояние заказа.
        event_seq двигаем — иначе клиент отбросит это событие как устаревшее.
        """
        if dialog_key not in OrderDialogAck.DIALOG_KEYS:
            raise OrderTransitionError(
                "unknown_dialog",
                f"Неизвестный диалог: {dialog_key}. Допустимые: {sorted(OrderDialogAck.DIALOG_KEYS)}",
            )

        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)
            if order.user_id != user.id:
                raise OrderTransitionError("forbidden", "Заказ принадлежит другому пользователю.", order)

            _ack, created = OrderDialogAck.objects.get_or_create(order=order, dialog_key=dialog_key)
            if not created:
                return order  # уже подтверждён — молча возвращаем, ретрай клиента безопасен

            _save_and_publish(order, [])

        transaction.on_commit(
            lambda: logger.info(
                "order_dialog_acknowledged %s",
                {"order_id": order.id, "dialog_key": dialog_key, "event_seq": order.event_seq},
            )
        )
        return order

    # ------------------------------------------------------------------ payment lifecycle

    @staticmethod
    def payment_started(order_id, *, provider):
        """
        Начало (создание) попытки оплаты. НЕ подтверждение платежа — только фиксирует факт,
        что клиент инициировал оплату, и проверяет, что окно оплаты ещё не закрыто (M1 п.10, Case E).
        Backend — authority: клиент не может создать платёжную попытку после payment_deadline_at
        никаким обходом UI.
        """
        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)
            prev_order_status, prev_payment_status = order.status_orders, order.payment_status

            if order.status_orders in ORDER_TERMINAL_STATUSES:
                raise OrderTransitionError(
                    "order_closed", "Заказ уже завершён или отменён — новую оплату начать нельзя.", order
                )
            if order.payment_status == Orders.PAID:
                raise OrderTransitionError("already_paid", "Заказ уже оплачен.", order)
            if order.pending_time_change_revision is not None:
                raise OrderTransitionError(
                    "time_change_confirmation_required",
                    "Сначала подтвердите новое время получения заказа.",
                    order,
                )

            now = timezone.now()
            if order.payment_deadline_at is not None and now > order.payment_deadline_at:
                raise OrderTransitionError(
                    "payment_window_closed",
                    "Окно оплаты истекло, новая попытка оплаты запрещена.",
                    order,
                )

            payment_status_transitioned = False
            if order.payment_status == Orders.NEW:
                order.payment_status = Orders.PENDING
                order.version += 1
                payment_status_transitioned = True

            if order.payment_started_at is None:
                order.payment_started_at = now

            if payment_status_transitioned:
                _save_and_publish(order, ["payment_status", "payment_started_at", "version"])
                # M7: с этого момента backend сам следит за оплатой — клиенту больше
                # не нужно опрашивать /api/payment/lifepay/status/. Планируем внутри
                # on_commit, чтобы задача не стартовала раньше коммита (тот же
                # инвариант, что и у timeout-задач в orders/signals.py).
                _schedule_payment_poll(order.id)
            else:
                # Ничего видимого клиенту не изменилось (payment_status тот же) —
                # событие не публикуем и event_seq не двигаем.
                order.save(update_fields=["payment_status", "payment_started_at", "version", "updated_at"])

        transaction.on_commit(
            lambda: _log_transition(
                order, operation="payment_started", actor_type="customer",
                prev_order_status=prev_order_status, prev_payment_status=prev_payment_status,
                extra={"provider": provider},
            )
        )
        return order

    @staticmethod
    def payment_succeeded(order_id, *, provider, provider_transaction_id, provider_paid_at=None, event_key=None):
        """
        Провайдер подтвердил оплату. Идемпотентно по (provider, event_key) — повторная
        доставка одного и того же события не меняет состояние второй раз (M1 п.21).

        Если заказ уже терминален (COMPLETED/CANCELED) — это late payment: payment_status
        фиксируется PAID, но order.status_orders НЕ трогается (M1 п.11) и заводится
        PaymentReconciliation.
        """
        with transaction.atomic():
            if event_key:
                _event, created = PaymentWebhookEvent.objects.get_or_create(
                    provider=provider, provider_event_id=event_key, defaults={"order_id": order_id}
                )
                if not created:
                    return Orders.objects.get(pk=order_id)  # уже обработано — no-op

            order = Orders.objects.select_for_update().get(pk=order_id)
            prev_order_status, prev_payment_status = order.status_orders, order.payment_status
            effective_paid_at = provider_paid_at or timezone.now()

            if order.status_orders in ORDER_TERMINAL_STATUSES:
                if order.status_orders == Orders.CANCELED:
                    PaymentReconciliation.objects.create(
                        order=order,
                        status=PaymentReconciliation.LATE_PAYMENT,
                        provider=provider,
                        provider_transaction_id=provider_transaction_id or "",
                        amount=order.full_price,
                        order_status_at_detection=order.status_orders,
                    )
                if order.payment_status != Orders.PAID:
                    order.payment_status = Orders.PAID
                    order.provider_paid_at = effective_paid_at
                    order.version += 1
                    # M7: late payment тоже публикуем — payment_status у клиента
                    # обязан сойтись с сервером, даже если сам заказ уже терминален.
                    _save_and_publish(order, ["payment_status", "provider_paid_at", "version"])
                    transaction.on_commit(
                        lambda: _log_transition(
                            order, operation="payment_succeeded_after_close", actor_type="provider",
                            prev_order_status=prev_order_status, prev_payment_status=prev_payment_status,
                            extra={"provider": provider, "late_payment": order.status_orders == Orders.CANCELED},
                        )
                    )
                return order

            if order.payment_status == Orders.PAID:
                return order  # уже зафиксировано — идемпотентный no-op

            order.payment_status = Orders.PAID
            order.provider_paid_at = effective_paid_at
            if order.status_orders in (Orders.NEW, Orders.WAITING):
                order.status_orders = Orders.IN_PROGRESS
            order.version += 1
            _save_and_publish(order, ["payment_status", "provider_paid_at", "status_orders", "version"])
            if (
                prev_order_status != Orders.IN_PROGRESS
                and order.status_orders == Orders.IN_PROGRESS
            ):
                _schedule_in_progress_notification(order)

        transaction.on_commit(
            lambda: _log_transition(
                order, operation="payment_succeeded", actor_type="provider",
                prev_order_status=prev_order_status, prev_payment_status=prev_payment_status,
                extra={"provider": provider},
            )
        )
        return order

    @staticmethod
    def payment_failed(order_id, *, provider, provider_transaction_id="", reason="", event_key=None):
        """Провайдер сообщил об отказе/просрочке платёжной попытки. Не отменяет заказ сам по себе —
        решение об отмене заказа принимает вызывающий код (обычно OrderStateService.cancel сразу вслед)."""
        with transaction.atomic():
            if event_key:
                _event, created = PaymentWebhookEvent.objects.get_or_create(
                    provider=provider, provider_event_id=event_key, defaults={"order_id": order_id}
                )
                if not created:
                    return Orders.objects.get(pk=order_id)

            order = Orders.objects.select_for_update().get(pk=order_id)
            prev_order_status, prev_payment_status = order.status_orders, order.payment_status

            if order.payment_status in (Orders.PAID, Orders.FAILED):
                return order  # уже в терминальном состоянии для payment — no-op

            order.payment_status = Orders.FAILED
            order.version += 1
            _save_and_publish(order, ["payment_status", "version"])

        transaction.on_commit(
            lambda: _log_transition(
                order, operation="payment_failed", actor_type="provider",
                prev_order_status=prev_order_status, prev_payment_status=prev_payment_status,
                extra={"provider": provider},
            )
        )
        return order

    @staticmethod
    def sync_payment_from_provider(order_id, *, provider_status_checker) -> bool:
        """
        Один цикл серверного опроса провайдера внутри платёжного окна (M7, шаг 4).

        Возвращает True, если имеет смысл опросить ещё раз (оплата всё ещё в
        процессе), и False, когда вопрос закрыт — задача по этому значению решает,
        планировать ли следующую итерацию. Сама ничего не отменяет: отмена по
        таймауту — работа evaluate_payment_deadline/finalize_payment_window, и
        дублировать это решение в двух местах нельзя.

        Никакой блокировки здесь нет намеренно: это чтение + делегирование в
        payment_succeeded, который берёт select_for_update сам.
        """
        from acquiring.providers import FAILED, PAID

        order = Orders.objects.get(pk=order_id)

        if order.status_orders in ORDER_TERMINAL_STATUSES:
            return False
        if order.payment_status in (Orders.PAID, Orders.FAILED):
            return False
        if order.payment_started_at is None:
            return False  # клиент так и не начал оплату — опрашивать нечего
        if order.payment_deadline_at is not None and timezone.now() > order.payment_deadline_at:
            return False  # окно закрыто, дальше отвечает deadline-задача

        provider_status = provider_status_checker(order)

        if provider_status.normalized_status == PAID:
            OrderStateService.payment_succeeded(
                order_id,
                provider="lifepay",
                provider_transaction_id="",
                provider_paid_at=provider_status.provider_paid_at,
            )
            return False
        if provider_status.normalized_status == FAILED:
            # Фиксируем отказ, но заказ не отменяем — это решение deadline-задачи.
            OrderStateService.payment_failed(
                order_id, provider="lifepay", reason="provider_failed_during_poll"
            )
            return False

        # PENDING или NOT_FOUND (инвойс ещё не создан) — продолжаем опрашивать.
        return True

    # ------------------------------------------------------------------ admin

    @staticmethod
    def admin_override(order_id, *, admin_user, new_order_status=None, new_payment_status=None, reason, request=None):
        """
        Явный bypass обычной state machine для администратора. Всегда требует reason и
        всегда пишет audit trail через admin_api.audit.log_admin_activity (M1 п.23).
        """
        if not reason or not reason.strip():
            raise OrderTransitionError("reason_required", "Для admin override обязательна причина.")

        if new_order_status and new_order_status not in dict(Orders.StatusOrders):
            raise OrderTransitionError("invalid_status_value", f"Недопустимое значение status_orders: {new_order_status}")
        if new_payment_status and new_payment_status not in dict(Orders.PaymentStatus):
            raise OrderTransitionError("invalid_status_value", f"Недопустимое значение payment_status: {new_payment_status}")

        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)
            old_order_status, old_payment_status = order.status_orders, order.payment_status

            if old_order_status == Orders.COMPLETED and new_order_status == Orders.CANCELED:
                raise OrderTransitionError(
                    "cannot_cancel_completed_order",
                    f"Нельзя отменить заказ #{order.id}, так как он уже выполнен (закрыт).",
                )

            if old_payment_status == Orders.PENDING and new_order_status and new_order_status != old_order_status:
                raise OrderTransitionError(
                    "cannot_change_status_awaiting_payment",
                    f"Нельзя изменить статус заказа #{order.id}, пока он ожидает оплаты.",
                )

            update_fields = ["version", "updated_at"]
            if new_order_status:
                order.status_orders = new_order_status
                update_fields.append("status_orders")
                if new_order_status == Orders.CANCELED:
                    order.cancellation_reason = reason
                    update_fields += ["cancellation_reason"]
            if new_payment_status:
                order.payment_status = new_payment_status
                update_fields.append("payment_status")

            order.version += 1
            # Публикуем realtime-событие только если реально изменилось business state
            # (status_orders/payment_status), а не на голый reason-only override.
            if new_order_status or new_payment_status:
                _save_and_publish(order, update_fields)
                if new_order_status and new_order_status != old_order_status:
                    _schedule_admin_status_notification(order, new_order_status)
            else:
                order.save(update_fields=update_fields)

        from admin_api.audit import log_admin_activity

        log_admin_activity(
            request,
            # AdminActivityLog.ACTION_CHOICES/max_length=20 (admin_api/models.py) не
            # содержит "STATUS_CHANGE_OVERRIDE" (22 симв.) — используем существующий
            # валидный choice, как это уже делают admin_api/views.py для других сущностей.
            "STATUS_CHANGE",
            "Orders",
            order.id,
            summary=f"Admin override заказа #{order.id}",
            changes={
                "old_status": old_order_status,
                "new_status": order.status_orders,
                "old_payment_status": old_payment_status,
                "new_payment_status": order.payment_status,
                "reason": reason,
            },
            actor=admin_user,
        )
        _log_transition(
            order, operation="admin_override", actor_type="admin",
            prev_order_status=old_order_status, prev_payment_status=old_payment_status,
        )
        return order

    # ------------------------------------------------------------------ barista confirmation SLA & payment deadline / grace (Celery)

    @staticmethod
    def evaluate_barista_confirmation_deadline(order_id):
        """
        Вызывается Celery-задачей на T0 + 90s (BARISTA_CONFIRMATION_TIMEOUT_SECONDS).
        Если бариста не подтвердил заказ (статус всё ещё New) — автоотмена с причиной
        для клиента о том, что кофейня не успела подтвердить заказ.
        """
        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)

            if order.status_orders in ORDER_TERMINAL_STATUSES:
                return order

            if order.status_orders != Orders.NEW:
                return order  # Уже принят (Waiting/In Progress/etc.) — no-op

            return OrderStateService.cancel(
                order_id,
                actor_type="system",
                reason="К сожалению, кофейня не успела вовремя подтвердить заказ 😔 Пожалуйста, попробуйте оформить его заново или выберите другую кофейню сети.",
            )

    @staticmethod
    def evaluate_payment_deadline(order_id, *, provider_status_checker):
        """
        Вызывается Celery-задачей на T0+90s (payment_deadline_at). provider_status_checker —
        callable(order) -> acquiring.providers.ProviderPaymentStatus, инжектируется вызывающим
        кодом (тесты подменяют его моком, реальный worker передаёт настоящий запрос к LifePay).
        """
        from acquiring.providers import PAID, PENDING

        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)

            if order.status_orders in ORDER_TERMINAL_STATUSES or order.payment_status == Orders.PAID:
                return order  # уже решено — no-op (в т.ч. защищает PAID от auto-cancel)
            if order.pending_time_change_revision is not None:
                return order  # оплата намеренно заблокирована до решения клиента

            if order.payment_started_at is None:
                # Case A: оплата не была начата вовсе.
                return OrderStateService.cancel(
                    order_id,
                    actor_type="system",
                    reason="Время на оплату вышло, заказ отменён 😔 Пожалуйста, оформите его заново.",
                )

            # Была активная попытка оплаты — проверяем провайдера прямо сейчас.
            provider_status = provider_status_checker(order)

            if provider_status.normalized_status == PAID:
                return OrderStateService.payment_succeeded(
                    order_id,
                    provider="lifepay",
                    provider_transaction_id="",
                    provider_paid_at=provider_status.provider_paid_at,
                )
            if provider_status.normalized_status == PENDING:
                # Case C: не отменяем — ждём finalize_payment_window на T0+120s.
                return order
            # FAILED / NOT_FOUND
            OrderStateService.payment_failed(order_id, provider="lifepay", reason="provider_failed_at_deadline")
            return OrderStateService.cancel(
                order_id,
                actor_type="system",
                reason="Банк не ответил вовремя 😕 Заказ отменён. Попробуйте оплатить ещё раз.",
            )

    @staticmethod
    def finalize_payment_window(order_id, *, provider_status_checker):
        """Вызывается Celery-задачей на T0+120s (payment_deadline_at + grace)."""
        from acquiring.providers import PAID, PENDING

        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)

            if order.status_orders in ORDER_TERMINAL_STATUSES or order.payment_status == Orders.PAID:
                return order
            if order.pending_time_change_revision is not None:
                return order

            provider_status = provider_status_checker(order)

            if provider_status.normalized_status == PAID:
                return OrderStateService.payment_succeeded(
                    order_id,
                    provider="lifepay",
                    provider_transaction_id="",
                    provider_paid_at=provider_status.provider_paid_at,
                )

            # FAILED / NOT_FOUND / всё ещё PENDING по истечении grace — заказ не может висеть
            # в неопределённом состоянии вечно (M1 п.14): отменяем. Если провайдер всё же
            # подтвердит оплату позже — это обычный late payment (payment_succeeded уже
            # умеет его принять и завести PaymentReconciliation, не воскрешая заказ).
            OrderStateService.payment_failed(order_id, provider="lifepay", reason="provider_unresolved_at_grace_end")
            return OrderStateService.cancel(
                order_id,
                actor_type="system",
                reason="Банк слишком долго обрабатывал платёж 😥 Мы отменили заказ, чтобы избежать ошибочных списаний.",
            )
