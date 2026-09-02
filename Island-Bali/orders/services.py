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

import logging

from django.db import transaction
from django.utils import timezone

from .models import Orders, PaymentReconciliation, PaymentWebhookEvent
from .realtime import publish_order_status_changed, snapshot_from_order
from .state_machine import (
    ORDER_TERMINAL_STATUSES,
    OrderTransitionError,
    is_order_transition_allowed,
)

logger = logging.getLogger("orders.state")


def _publish_realtime_on_commit(order):
    """Снапшот строится сейчас (внутри atomic, пока order залочен и уже сохранён),
    публикация — только после реального commit (M3, п.27, п.40)."""
    snapshot = snapshot_from_order(order)
    transaction.on_commit(lambda: publish_order_status_changed(snapshot))


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
            order.version += 1
            order.save(update_fields=["status_orders", "staff", "version", "updated_at"])
            _publish_realtime_on_commit(order)

        transaction.on_commit(
            lambda: _log_transition(
                order, operation="accept", actor_type="staff",
                prev_order_status=prev_order_status, prev_payment_status=prev_payment_status,
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
            order.isOrderCancelled = True
            order.version += 1
            order.save(
                update_fields=[
                    "status_orders", "cancellation_reason", "isOrderCancelled", "version", "updated_at",
                ]
            )
            _publish_realtime_on_commit(order)

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
            order.save(update_fields=["status_orders", "staff", "version", "updated_at"])
            _publish_realtime_on_commit(order)

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
    def client_confirmed(order_id, *, user):
        """Клиент подтвердил заказ после изменения времени бариста. Не меняет status_orders."""
        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)
            if order.user_id != user.id:
                raise OrderTransitionError("forbidden", "Заказ принадлежит другому пользователю.", order)
            if order.client_confirmed:
                return order  # идемпотентно
            prev_order_status, prev_payment_status = order.status_orders, order.payment_status
            order.client_confirmed = True
            order.version += 1
            order.save(update_fields=["client_confirmed", "version", "updated_at"])

        transaction.on_commit(
            lambda: _log_transition(
                order, operation="client_confirmed", actor_type="customer",
                prev_order_status=prev_order_status, prev_payment_status=prev_payment_status,
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

            order.save(update_fields=["payment_status", "payment_started_at", "version", "updated_at"])
            if payment_status_transitioned:
                _publish_realtime_on_commit(order)

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
                    order.save(update_fields=["payment_status", "provider_paid_at", "version", "updated_at"])
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
            order.save(
                update_fields=["payment_status", "provider_paid_at", "status_orders", "version", "updated_at"]
            )
            _publish_realtime_on_commit(order)

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
            order.save(update_fields=["payment_status", "version", "updated_at"])
            _publish_realtime_on_commit(order)

        transaction.on_commit(
            lambda: _log_transition(
                order, operation="payment_failed", actor_type="provider",
                prev_order_status=prev_order_status, prev_payment_status=prev_payment_status,
                extra={"provider": provider},
            )
        )
        return order

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

            update_fields = ["version", "updated_at"]
            if new_order_status:
                order.status_orders = new_order_status
                update_fields.append("status_orders")
                if new_order_status == Orders.CANCELED:
                    order.cancellation_reason = reason
                    order.isOrderCancelled = True
                    update_fields += ["cancellation_reason", "isOrderCancelled"]
            if new_payment_status:
                order.payment_status = new_payment_status
                update_fields.append("payment_status")

            order.version += 1
            order.save(update_fields=update_fields)
            # Публикуем realtime-событие только если реально изменилось business state
            # (status_orders/payment_status), а не на голый reason-only override.
            if new_order_status or new_payment_status:
                _publish_realtime_on_commit(order)

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

    # ------------------------------------------------------------------ payment deadline / grace (Celery)

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

            if order.payment_started_at is None:
                # Case A: оплата не была начата вовсе.
                return OrderStateService.cancel(
                    order_id, actor_type="system", reason="Автоматическая отмена: оплата не была начата за 90 секунд."
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
                order_id, actor_type="system", reason="Автоматическая отмена: провайдер не подтвердил оплату к дедлайну."
            )

    @staticmethod
    def finalize_payment_window(order_id, *, provider_status_checker):
        """Вызывается Celery-задачей на T0+120s (payment_deadline_at + grace)."""
        from acquiring.providers import PAID, PENDING

        with transaction.atomic():
            order = Orders.objects.select_for_update().get(pk=order_id)

            if order.status_orders in ORDER_TERMINAL_STATUSES or order.payment_status == Orders.PAID:
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
                reason="Автоматическая отмена: оплата не подтверждена провайдером в течение grace-периода.",
            )
