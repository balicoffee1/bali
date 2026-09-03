"""
Realtime order event publisher (M3, расширен в M7).

Что изменилось в M7 и почему
----------------------------
Раньше событие несло 6 технических полей (order_id/status/payment/version/updated_at),
и клиент по нему шёл в REST за настоящим состоянием заказа — то есть WebSocket не
отменял HTTP-запрос, а порождал его. Теперь событие несёт **полный снапшот заказа**
в том же формате, что элемент REST-списка, и клиенту больше некуда ходить.

Два адресата — две формы payload'а
----------------------------------
Одно и то же событие уходит в группу покупателя (orders.user.{id}) и в группу
кофейни (orders.shop.{id}), но это РАЗНЫЕ клиенты с разными экранами: покупателю
нужен его заказ целиком, персоналу — карточка заказа для колонок (состав корзины,
телефон клиента). Раньше в обе группы уходил один и тот же тонкий payload, и это
работало только потому, что payload был transport-level.

Ключевой момент — поле "audience". Мобильное приложение у покупателя и у бариста
одно и то же, и staff-пользователь держит ОДНО соединение, подписанное сразу на обе
группы: свою user-группу и shop-группу своей кофейни. Без явного маркера его
customer-блок применил бы чужой заказ (пришедший по shop-группе) как свой последний
заказ — то есть показал бы бариста диалоги по заказу постороннего человека. Поэтому
audience проставляет сервер, а клиент по нему решает, в какой слой состояния класть
событие. Это не про утечку данных между пользователями (в обе группы уходит один и
тот же заказ, а телефон клиента персонал и так видит в /api/staff/orders/), а про
корректную маршрутизацию на клиенте.

Инвариант надёжности сохраняется прежний: publish_order_status_changed никогда не
поднимает исключение наружу и никак не влияет на исход DB-транзакции — недоступность
Redis не должна ломать уже совершённый commit (order DB state = source of truth,
realtime = best effort, без гарантии доставки и без durable replay).

Почему сериализация происходит ПОСЛЕ commit
-------------------------------------------
OrderStateService регистрирует publish через transaction.on_commit, и полный снапшот
читается уже здесь, отдельным запросом к закоммиченным данным. Внутри atomic-блока
этого делать не стоит: сериализация заказа тянет связанные таблицы, а строка заказа
в этот момент залочена select_for_update. Как следствие, снапшот может оказаться
СВЕЖЕЕ, чем событие, которое его вызвало (если следом прошёл ещё один переход) —
это и нужно: клиент всегда сходится к актуальному состоянию, а event_seq в payload
берётся из того же прочитанного заказа, а не из устаревшего дескриптора события.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("orders.realtime")

ORDER_STATUS_CHANGED = "order.status_changed"
ORDER_SNAPSHOT = "order.snapshot"
ORDER_SHOP_SNAPSHOT = "orders.shop_snapshot"

AUDIENCE_CUSTOMER = "customer"
AUDIENCE_STAFF = "staff"

USER_GROUP = "orders.user.{user_id}"
SHOP_GROUP = "orders.shop.{shop_id}"


@dataclass(frozen=True)
class OrderRealtimeSnapshot:
    """
    Дескриптор события, а не его payload.

    Строится внутри транзакции (пока order залочен и уже сохранён) и служит двум
    целям: маршрутизация (в какие группы слать) и диагностика (что именно
    изменилось). Сам payload собирается после commit из свежепрочитанного заказа —
    см. докстринг модуля.
    """

    order_id: int
    user_id: Optional[int]
    coffee_shop_id: Optional[int]
    status_orders: str
    payment_status: str
    version: int
    event_seq: int
    updated_at: str
    cancellation_reason: str = ""


def snapshot_from_order(order) -> OrderRealtimeSnapshot:
    updated_at = order.updated_at
    return OrderRealtimeSnapshot(
        order_id=order.id,
        user_id=order.user_id,
        coffee_shop_id=order.coffee_shop_id,
        status_orders=order.status_orders,
        payment_status=order.payment_status,
        version=order.version,
        event_seq=order.event_seq,
        updated_at=updated_at.isoformat() if updated_at else "",
        cancellation_reason=order.cancellation_reason or "",
    )


# ---------------------------------------------------------------------------
# Сериализация заказа под конкретного адресата
# ---------------------------------------------------------------------------


def _orders_queryset():
    """select_related на всё, что читают оба сериализатора, — один запрос вместо пяти."""
    from .models import Orders

    return Orders.objects.select_related(
        "city_choose", "coffee_shop", "cart", "user"
    ).prefetch_related("dialog_acks")


def serialize_for_customer(order) -> dict:
    from .serializers import OrderRealtimeSerializer

    return OrderRealtimeSerializer(order).data


def serialize_for_staff(order) -> dict:
    from staff.serializers import PendingOrdersAcceptSerializer

    data = PendingOrdersAcceptSerializer(order).data
    # Персоналу тоже нужен event_seq — дедупликация событий на клиенте одинаковая
    # для обоих экранов, а PendingOrdersAcceptSerializer про него не знает.
    data["event_seq"] = order.event_seq
    data["version"] = order.version
    return data


def shop_snapshot_payload(shop_id) -> dict:
    """
    Полное состояние экрана смены — отправляется один раз, при подключении.

    Дальше по этому же соединению идут дельты по одному заказу
    (order.status_changed с audience=staff), и клиент двигает заказ между
    колонками сам. Почему так, а не «полное состояние на каждое событие»:
    колонка «Выполненные» ничем не ограничена по времени и растёт бесконечно,
    так что пересылать её целиком на каждый переход — это стоимость, которая
    со временем только увеличивается.

    Состав колонок берётся из staff/queries.py — тех же функций, из которых
    отвечает REST, поэтому «что видно на экране» не зависит от транспорта.
    """
    from django.utils import timezone

    from staff.queries import (
        SHIFT_WINDOW,
        orders_in_shift_window,
        orders_with_status,
        shift_aggregates,
    )
    from staff.serializers import PendingOrdersAcceptSerializer

    from .models import Orders

    def serialize(queryset):
        return PendingOrdersAcceptSerializer(queryset, many=True).data

    return {
        "type": ORDER_SHOP_SNAPSHOT,
        "audience": AUDIENCE_STAFF,
        "coffee_shop_id": shop_id,
        # Окно приезжает в payload'е явно: клиент по нему решает, попадает ли
        # заказ из дельты в список новых, и это то же число, которым сервер
        # отфильтровал снапшот.
        "shift_window_minutes": int(SHIFT_WINDOW.total_seconds() // 60),
        "orders": serialize(
            orders_in_shift_window(
                city_id=None,
                coffee_shop_id=shop_id,
                sorting_time=timezone.now() - SHIFT_WINDOW,
            )
        ),
        "columns": {
            status: serialize(
                orders_with_status(city_id=None, coffee_shop_id=shop_id, status=status)
            )
            for status in (Orders.WAITING, Orders.IN_PROGRESS, Orders.COMPLETED)
        },
        **shift_aggregates(),
    }


def customer_snapshot_payload(order) -> dict:
    """
    Кадр order.snapshot для покупателя: список из 0 или 1 заказа.

    Список, а не объект, — чтобы совпадать по форме с состоянием клиента
    (MatchingState<List<OrderView>>) и с REST-ответом. Ровно один заказ (самый
    свежий по id): весь клиентский UI работает с "моим последним заказом", а
    отдавать всю историю на каждом коннекте незачем.
    """
    return {
        "type": ORDER_SNAPSHOT,
        "audience": AUDIENCE_CUSTOMER,
        "orders": [serialize_for_customer(order)] if order is not None else [],
    }


def latest_order_for_user(user_id):
    return _orders_queryset().filter(user_id=user_id).order_by("id").last()


# ---------------------------------------------------------------------------
# Публикация
# ---------------------------------------------------------------------------


def publish_order_status_changed(snapshot: OrderRealtimeSnapshot) -> None:
    """Best-effort fan-out — вызывается только из transaction.on_commit (M3, п.27)."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from .models import Orders

    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning(
            "order_realtime_event_failed %s",
            {"order_id": snapshot.order_id, "event_seq": snapshot.event_seq, "reason": "no_channel_layer"},
        )
        return

    try:
        order = _orders_queryset().get(pk=snapshot.order_id)
    except Orders.DoesNotExist:
        logger.warning(
            "order_realtime_event_failed %s",
            {"order_id": snapshot.order_id, "reason": "order_gone"},
        )
        return

    targets = []
    if snapshot.user_id:
        targets.append(
            (AUDIENCE_CUSTOMER, USER_GROUP.format(user_id=snapshot.user_id), serialize_for_customer)
        )
    if snapshot.coffee_shop_id:
        targets.append(
            (AUDIENCE_STAFF, SHOP_GROUP.format(shop_id=snapshot.coffee_shop_id), serialize_for_staff)
        )

    for audience, group_name, serialize in targets:
        try:
            payload = {
                "type": ORDER_STATUS_CHANGED,
                "audience": audience,
                "order": serialize(order),
            }
            if audience == AUDIENCE_STAFF:
                # Кофейня в кадре обязательна: сотрудник может работать в
                # нескольких точках, и тогда по одному соединению приходят
                # дельты обеих — экран смены должен взять только свою.
                payload["coffee_shop_id"] = snapshot.coffee_shop_id
                # Счётчики и суммы для карточки смены: их нельзя посчитать из
                # колонок (они считаются по всей таблице), поэтому едут вместе
                # с дельтой — иначе после подключения они бы застыли.
                from staff.queries import shift_aggregates

                payload.update(shift_aggregates())
            async_to_sync(channel_layer.group_send)(
                group_name, {"type": ORDER_STATUS_CHANGED, "payload": payload}
            )
        except Exception:
            logger.exception(
                "order_realtime_event_failed %s",
                {"order_id": snapshot.order_id, "event_seq": order.event_seq, "group_type": audience},
            )
        else:
            logger.info(
                "order_realtime_event_published %s",
                {"order_id": snapshot.order_id, "event_seq": order.event_seq, "group_type": audience},
            )
