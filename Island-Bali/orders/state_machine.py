"""
Каноническая state machine заказа Island Bali (M1).

ORDER STATUS и PAYMENT STATUS — две независимые машины состояний, которые
меняются вместе только в конкретных, явно перечисленных ниже точках (см.
orders.services.OrderStateService.payment_succeeded). Ни один вызывающий код
не должен присваивать order.status_orders / order.payment_status напрямую —
единственная точка мутации — OrderStateService.

Восстановлено из фактического использования статусов в проекте на момент
аудита (docs/order-status-websocket-audit.md), не выдумано заново:

    Orders.StatusOrders  = New, Waiting, In Progress, Completed, Canceled
    Orders.PaymentStatus = New, Pending, Paid, Failed
    (New в PaymentStatus == "оплата ещё не начата", т.е. NOT_STARTED)
"""
from __future__ import annotations

from .models import Orders

# ---------------------------------------------------------------------------
# Order state machine
# ---------------------------------------------------------------------------

ORDER_TERMINAL_STATUSES = frozenset({Orders.COMPLETED, Orders.CANCELED})

# target_status -> множество статусов, из которых переход разрешён
ORDER_TRANSITIONS = {
    Orders.WAITING: frozenset({Orders.NEW}),
    Orders.IN_PROGRESS: frozenset({Orders.WAITING}),
    Orders.COMPLETED: frozenset({Orders.IN_PROGRESS}),
    Orders.CANCELED: frozenset({Orders.NEW, Orders.WAITING, Orders.IN_PROGRESS}),
}


def is_order_transition_allowed(current_status: str, target_status: str) -> bool:
    """Обычный (не admin_override) переход status_orders."""
    if current_status in ORDER_TERMINAL_STATUSES:
        return False
    allowed_sources = ORDER_TRANSITIONS.get(target_status)
    if allowed_sources is None:
        return False
    return current_status in allowed_sources


# ---------------------------------------------------------------------------
# Payment state machine
# ---------------------------------------------------------------------------

PAYMENT_TERMINAL_STATUSES = frozenset({Orders.PAID, Orders.FAILED})
PAYMENT_NOT_STARTED = Orders.NEW  # алиас для читаемости вызывающего кода

PAYMENT_TRANSITIONS = {
    Orders.PENDING: frozenset({Orders.NEW}),
    # PAID разрешён и из NEW: провайдер может подтвердить оплату быстрее, чем
    # наш backend успел записать payment_started (см. payment_succeeded).
    Orders.PAID: frozenset({Orders.NEW, Orders.PENDING}),
    Orders.FAILED: frozenset({Orders.NEW, Orders.PENDING}),
}


def is_payment_transition_allowed(current_status: str, target_status: str) -> bool:
    if current_status in PAYMENT_TERMINAL_STATUSES:
        return False
    allowed_sources = PAYMENT_TRANSITIONS.get(target_status)
    if allowed_sources is None:
        return False
    return current_status in allowed_sources


# ---------------------------------------------------------------------------
# Payment timing policy (M1, п.7-10)
# ---------------------------------------------------------------------------

PAYMENT_WINDOW_SECONDS = 90
GRACE_PERIOD_SECONDS = 30
FINAL_DEADLINE_SECONDS = PAYMENT_WINDOW_SECONDS + GRACE_PERIOD_SECONDS  # 120


class OrderTransitionError(Exception):
    """
    Доменная ошибка перехода. code — машиночитаемая причина для маппинга в HTTP-статус
    вызывающим кодом (view/serializer), а не сам HTTP-статус — сервис не знает про HTTP.
    """

    def __init__(self, code: str, message: str, order=None):
        self.code = code
        self.message = message
        self.order = order
        super().__init__(message)
