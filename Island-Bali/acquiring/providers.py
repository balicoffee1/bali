"""
Единая нормализация статуса платежа LifePay.

Раньше HTTP-запрос к LIFEPAY_STATUS_URL и трактовка кодов статуса были
продублированы в acquiring.views.check_lifepay_status и (частично, с
разными правилами) в webhook-обработчиках. Теперь это одно место —
используется и вьюхой опроса, и Celery-таймаутами (orders.tasks), и
верификацией webhook'а (acquiring.views.lifepay_callback), т.к. у LifePay
нет задокументированной подписи callback'а — вместо изобретения
криптографической схемы, которую провайдер может не поддерживать, каждый
входящий webhook перепроверяется прямым запросом статуса через API LifePay
(см. docs/order-status-websocket-audit.md, M0 п.3.4).

Коды LifePay (как использовались в проекте до M1): 10 — оплачен,
15 — в обработке/ожидании, 20/30 — отменён/просрочен.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests
from django.utils import timezone

LIFEPAY_STATUS_URL = "https://api.life-pay.ru/v1/bill/status"

PAID = "PAID"
PENDING = "PENDING"
FAILED = "FAILED"
NOT_FOUND = "NOT_FOUND"

logger = logging.getLogger("acquiring.providers")


@dataclass(frozen=True)
class ProviderPaymentStatus:
    normalized_status: str  # PAID | PENDING | FAILED | NOT_FOUND
    provider_paid_at: Optional[object] = None  # datetime | None
    raw_status_code: Optional[int] = None
    message: str = ""


def _normalize_status_code(status_code) -> str:
    if status_code == 10:
        return PAID
    if status_code == 15:
        return PENDING
    if status_code in (20, 30):
        return FAILED
    return NOT_FOUND


def get_lifepay_transaction_status(coffee_shop, transaction_number: str) -> ProviderPaymentStatus:
    """
    Прямой запрос статуса конкретной транзакции к API LifePay.
    Не пишет ничего в БД — чистая функция запроса, решение принимает вызывающий код
    (orders.services.OrderStateService).
    """
    params = {
        "apikey": coffee_shop.lifepay_api_key,
        "login": coffee_shop.lifepay_login,
        "number": transaction_number,
    }
    try:
        response = requests.get(LIFEPAY_STATUS_URL, params=params, timeout=10)
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("lifepay status check failed transaction=%s error=%s", transaction_number, exc)
        return ProviderPaymentStatus(normalized_status=PENDING, message="provider_unreachable")

    if result.get("code") != 0:
        return ProviderPaymentStatus(normalized_status=NOT_FOUND, message=str(result.get("message", "")))

    transaction_data = result.get("data", {}).get(transaction_number, {})
    status_code = transaction_data.get("status")

    return ProviderPaymentStatus(
        normalized_status=_normalize_status_code(status_code),
        provider_paid_at=timezone.now() if status_code == 10 else None,
        raw_status_code=status_code,
        message=transaction_data.get("msg", ""),
    )


def get_latest_invoice(order):
    from .models import LifepayInvoice

    return LifepayInvoice.objects.filter(order=order).order_by("-created_at").first()
