"""
Realtime order event publisher (M3).

OrderStateService строит OrderRealtimeSnapshot внутри своего transaction.atomic()
блока (сразу после реального .save(), пока order ещё залочен и его поля точно
отражают закоммиченное изменение) и регистрирует publish_order_status_changed(snapshot)
через transaction.on_commit — см. orders/services.py. Снапшот иммутабелен: после
commit никто не перечитывает мутируемый ORM-объект.

Инвариант: publish_order_status_changed никогда не поднимает исключение наружу и
никак не влияет на исход DB-транзакции — WebSocket/Redis недоступность не должна
ломать уже совершённый commit (order DB state = source of truth, realtime = best effort,
без гарантии доставки и без durable replay — см. финальный отчёт).

OrderStateService не импортирует ничего из orders.consumers — Service знает только
об этом модуле-абстракции, а не о consumer/Channels API напрямую.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("orders.realtime")

ORDER_STATUS_CHANGED = "order.status_changed"


@dataclass(frozen=True)
class OrderRealtimeSnapshot:
    order_id: int
    user_id: Optional[int]
    coffee_shop_id: Optional[int]
    status_orders: str
    payment_status: str
    version: int
    updated_at: str
    cancellation_reason: str = ""

    def to_payload(self) -> dict:
        payload = {
            "type": ORDER_STATUS_CHANGED,
            "order_id": self.order_id,
            "status_orders": self.status_orders,
            "payment_status": self.payment_status,
            "version": self.version,
            "updated_at": self.updated_at,
        }
        if self.cancellation_reason:
            payload["cancellation_reason"] = self.cancellation_reason
        return payload


def snapshot_from_order(order) -> OrderRealtimeSnapshot:
    updated_at = order.updated_at
    return OrderRealtimeSnapshot(
        order_id=order.id,
        user_id=order.user_id,
        coffee_shop_id=order.coffee_shop_id,
        status_orders=order.status_orders,
        payment_status=order.payment_status,
        version=order.version,
        updated_at=updated_at.isoformat() if updated_at else "",
        cancellation_reason=order.cancellation_reason or "",
    )


def publish_order_status_changed(snapshot: OrderRealtimeSnapshot) -> None:
    """Best-effort fan-out — вызывается только из transaction.on_commit (M3, п.27)."""
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning(
            "order_realtime_event_failed %s",
            {"order_id": snapshot.order_id, "version": snapshot.version, "reason": "no_channel_layer"},
        )
        return

    payload = snapshot.to_payload()
    targets = []
    if snapshot.user_id:
        targets.append(("customer", f"orders.user.{snapshot.user_id}"))
    if snapshot.coffee_shop_id:
        targets.append(("staff", f"orders.shop.{snapshot.coffee_shop_id}"))

    for group_type, group_name in targets:
        try:
            async_to_sync(channel_layer.group_send)(
                group_name, {"type": ORDER_STATUS_CHANGED, "payload": payload}
            )
        except Exception:
            logger.exception(
                "order_realtime_event_failed %s",
                {"order_id": snapshot.order_id, "version": snapshot.version, "group_type": group_type},
            )
        else:
            logger.info(
                "order_realtime_event_published %s",
                {"order_id": snapshot.order_id, "version": snapshot.version, "group_type": group_type},
            )
