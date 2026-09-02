"""
WebSocket consumer заказов (M2).

Единый endpoint /ws/orders/ — роль клиента (customer/staff) определяется сервером
по scope["user"], а не декларируется клиентом. Клиент никогда не выбирает
user_id/coffee_shop_id/order_id для подписки (M2, п.12-14).

WS — только notification transport: единственная входящая команда — heartbeat
"ping"/"pong". Никаких order.cancel/accept/complete и т.п. — бизнес-мутации
остаются исключительно на REST/Celery/OrderStateService (M2, п.22).

Topology (кто в какой группе) хранится в Channels/Redis, а не в Python-процессе —
безопасно для нескольких ASGI worker'ов (M2, п.17-19).
"""
from __future__ import annotations

import asyncio
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger("orders.consumers")

# Channels group name: только [a-zA-Z0-9_.-], до 100 символов — числовые ID укладываются
# с большим запасом.
USER_GROUP = "orders.user.{user_id}"
SHOP_GROUP = "orders.shop.{shop_id}"

CLOSE_UNAUTHENTICATED = 4001
CLOSE_TOKEN_EXPIRED = 4002


@database_sync_to_async
def _staff_shop_ids(user_id: int) -> list[int]:
    from staff.models import Staff

    return list(
        Staff.objects.filter(users_id=user_id, place_of_work_id__isnull=False)
        .values_list("place_of_work_id", flat=True)
        .distinct()
    )


class OrderNotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            logger.info("ws_auth_failed %s", {"reason": "anonymous"})
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return

        self.token_exp = self.scope.get("token_exp")
        self.groups_joined = [USER_GROUP.format(user_id=user.id)]

        shop_ids = await _staff_shop_ids(user.id)
        self.groups_joined += [SHOP_GROUP.format(shop_id=shop_id) for shop_id in shop_ids]

        for group in self.groups_joined:
            await self.channel_layer.group_add(group, self.channel_name)

        await self.accept()
        logger.info("ws_connected %s", {"user_id": user.id, "groups": len(self.groups_joined)})
        for group in self.groups_joined:
            logger.info("ws_group_joined %s", {"user_id": user.id, "group_type": group.split(".")[1]})

        self._expiry_task = asyncio.ensure_future(self._close_when_token_expires())

    async def _close_when_token_expires(self):
        if not self.token_exp:
            return
        delay = max(0.0, self.token_exp - time.time())
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        logger.info("ws_disconnected %s", {"reason": "token_expired"})
        await self.close(code=CLOSE_TOKEN_EXPIRED)

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        try:
            content = await self.decode_json(text_data)
        except Exception:
            await self.send_json({"type": "error", "code": "invalid_json"})
            return
        await self.receive_json(content, **kwargs)

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type") if isinstance(content, dict) else None
        if msg_type == "ping":
            await self.send_json({"type": "pong"})
            return
        # Неизвестный/business-mutation тип (order.cancel и т.п.) — WS не умеет
        # мутировать состояние заказа, поэтому просто сообщаем клиенту об ошибке,
        # не падая и не выполняя никакого действия.
        await self.send_json({"type": "error", "code": "unknown_type"})

    async def order_status_changed(self, event):
        """Group message handler — channels маппит type "order.status_changed" сюда."""
        await self.send_json(event["payload"])

    async def disconnect(self, close_code):
        expiry_task = getattr(self, "_expiry_task", None)
        if expiry_task is not None:
            expiry_task.cancel()

        for group in getattr(self, "groups_joined", []):
            await self.channel_layer.group_discard(group, self.channel_name)

        logger.info("ws_disconnected %s", {"close_code": close_code})
