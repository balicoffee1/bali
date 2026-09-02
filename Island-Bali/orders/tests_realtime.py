"""
M2/M3: WebSocket infrastructure (auth, isolation, heartbeat) + realtime order event
publication semantics (commit/rollback/no-op/duplicate).

Две категории тестов используют разные Django TestCase базовые классы намеренно:

* WebSocket-тесты (auth/isolation/multi-device) — TransactionTestCase. Consumer читает
  БД через channels.db.database_sync_to_async, то есть из отдельного потока со своим
  DB-соединением; обычный TestCase (который держит тест в незакоммиченной транзакции)
  не был бы виден этому потоку. TransactionTestCase коммитит по-настоящему — то, что
  нужно и для видимости между "потоками", и одновременно даёт честную on_commit-семантику.

* Публикационные тесты (commit -> событие, rollback -> нет события, no-op -> нет события)
  — обычный TestCase + self.captureOnCommitCallbacks(execute=True). Это официальный
  Django-паттерн именно для проверки transaction.on_commit(...) без реального commit —
  он не подделывает семантику: callback, вычеркнутый Django при откате вложенной
  транзакции, captureOnCommitCallbacks и не увидит. Быстрее TransactionTestCase и не
  требует Channels/Redis вообще (сам publish_order_status_changed замокан — тестируем
  именно "OrderStateService вызывает publish ровно когда должен", а не транспорт).
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.db import transaction
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from cart.models import ShoppingCart
from coffee_shop.models import City
from island_bali.asgi import application
from orders.models import Orders
from orders.services import OrderStateService
from orders.state_machine import OrderTransitionError
from orders.tests import make_coffee_shop
from staff.models import Staff
from users.models import CustomUser

IN_MEMORY_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


class RealtimeFixtureMixin:
    def _make_fixtures(self):
        self.city = City.objects.create(name="Moscow")
        self.coffee_shop = make_coffee_shop(self.city)
        self.other_shop = make_coffee_shop(City.objects.create(name="Kazan"))

        self.customer = CustomUser.objects.create_user(login="+79990001001", password="pw")
        self.other_customer = CustomUser.objects.create_user(login="+79990001002", password="pw")
        self.staff_user = CustomUser.objects.create_user(login="+79990001003", password="pw")
        self.other_shop_staff_user = CustomUser.objects.create_user(login="+79990001004", password="pw")

        self.staff = Staff.objects.create(users=self.staff_user, place_of_work=self.coffee_shop)
        self.other_shop_staff = Staff.objects.create(
            users=self.other_shop_staff_user, place_of_work=self.other_shop
        )

        self.cart = ShoppingCart.objects.create(user=self.customer, is_active=True)

    def make_order(self, **overrides):
        defaults = dict(
            user=self.customer,
            city_choose=self.city,
            coffee_shop=self.coffee_shop,
            cart=self.cart,
            full_price=Decimal("300.00"),
        )
        defaults.update(overrides)
        return Orders.objects.create(**defaults)

    @staticmethod
    def token_for(user):
        return str(RefreshToken.for_user(user).access_token)

    @staticmethod
    def auth_headers(token):
        return [(b"authorization", f"Bearer {token}".encode())]


# ---------------------------------------------------------------------------
# M2: аутентификация WebSocket handshake
# ---------------------------------------------------------------------------


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYERS)
class WebSocketAuthenticationTests(RealtimeFixtureMixin, TransactionTestCase):
    def setUp(self):
        self._make_fixtures()

    async def test_anonymous_connection_is_rejected(self):
        communicator = WebsocketCommunicator(application, "/ws/orders/")
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_invalid_token_is_rejected(self):
        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers("garbage.token.value")
        )
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_expired_token_is_rejected(self):
        token = AccessToken.for_user(self.customer)
        token.set_exp(lifetime=timedelta(seconds=-30))
        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(str(token))
        )
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_valid_customer_token_is_accepted(self):
        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.customer))
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_valid_staff_token_is_accepted(self):
        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.staff_user))
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_heartbeat_ping_pong(self):
        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.customer))
        )
        await communicator.connect()
        await communicator.send_json_to({"type": "ping"})
        response = await communicator.receive_json_from(timeout=2)
        self.assertEqual(response, {"type": "pong"})
        await communicator.disconnect()

    async def test_unknown_frame_type_does_not_crash_connection(self):
        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.customer))
        )
        await communicator.connect()
        # WS не умеет мутировать бизнес-состояние — такой команды у consumer'а просто нет.
        await communicator.send_json_to({"type": "order.cancel", "order_id": 999})
        response = await communicator.receive_json_from(timeout=2)
        self.assertEqual(response["type"], "error")
        # соединение осталось живым
        await communicator.send_json_to({"type": "ping"})
        pong = await communicator.receive_json_from(timeout=2)
        self.assertEqual(pong, {"type": "pong"})
        await communicator.disconnect()

    async def test_malformed_json_does_not_crash_connection(self):
        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.customer))
        )
        await communicator.connect()
        await communicator.send_to(text_data="{not valid json")
        response = await communicator.receive_json_from(timeout=2)
        self.assertEqual(response["type"], "error")
        await communicator.disconnect()


# ---------------------------------------------------------------------------
# M2: изоляция подписок (customer/staff) + несколько устройств
# ---------------------------------------------------------------------------


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYERS)
class CustomerIsolationTests(RealtimeFixtureMixin, TransactionTestCase):
    def setUp(self):
        self._make_fixtures()
        self.order_a = self.make_order(user=self.customer)
        cart_b = ShoppingCart.objects.create(user=self.other_customer, is_active=True)
        self.order_b = self.make_order(user=self.other_customer, cart=cart_b)

    async def test_customer_a_receives_own_event_customer_b_does_not(self):
        comm_a = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.customer))
        )
        comm_b = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.other_customer))
        )
        self.assertTrue((await comm_a.connect())[0])
        self.assertTrue((await comm_b.connect())[0])

        await database_sync_to_async(OrderStateService.accept)(self.order_a.id, staff_user=None)

        event = await comm_a.receive_json_from(timeout=2)
        self.assertEqual(event["order_id"], self.order_a.id)
        self.assertEqual(event["status_orders"], Orders.WAITING)

        self.assertTrue(await comm_b.receive_nothing(timeout=0.5))

        await comm_a.disconnect()
        await comm_b.disconnect()


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYERS)
class StaffIsolationTests(RealtimeFixtureMixin, TransactionTestCase):
    def setUp(self):
        self._make_fixtures()
        self.order_shop_a = self.make_order(coffee_shop=self.coffee_shop)
        cart_b = ShoppingCart.objects.create(user=self.customer, is_active=True)
        self.order_shop_b = self.make_order(coffee_shop=self.other_shop, cart=cart_b)

    async def test_staff_a_and_staff_b_only_see_their_own_shop(self):
        comm_staff_a = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.staff_user))
        )
        comm_staff_b = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.other_shop_staff_user))
        )
        self.assertTrue((await comm_staff_a.connect())[0])
        self.assertTrue((await comm_staff_b.connect())[0])

        await database_sync_to_async(OrderStateService.accept)(
            self.order_shop_a.id, staff_user=self.staff_user
        )
        event_a = await comm_staff_a.receive_json_from(timeout=2)
        self.assertEqual(event_a["order_id"], self.order_shop_a.id)
        self.assertTrue(await comm_staff_b.receive_nothing(timeout=0.5))

        await database_sync_to_async(OrderStateService.accept)(
            self.order_shop_b.id, staff_user=self.other_shop_staff_user
        )
        event_b = await comm_staff_b.receive_json_from(timeout=2)
        self.assertEqual(event_b["order_id"], self.order_shop_b.id)
        self.assertTrue(await comm_staff_a.receive_nothing(timeout=0.5))

        await comm_staff_a.disconnect()
        await comm_staff_b.disconnect()


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYERS)
class MultiDeviceFanoutTests(RealtimeFixtureMixin, TransactionTestCase):
    def setUp(self):
        self._make_fixtures()
        self.order = self.make_order()

    async def test_all_devices_of_same_user_receive_event(self):
        token = self.token_for(self.customer)
        comm1 = WebsocketCommunicator(application, "/ws/orders/", headers=self.auth_headers(token))
        comm2 = WebsocketCommunicator(application, "/ws/orders/", headers=self.auth_headers(token))
        self.assertTrue((await comm1.connect())[0])
        self.assertTrue((await comm2.connect())[0])

        await database_sync_to_async(OrderStateService.accept)(self.order.id, staff_user=None)

        event1 = await comm1.receive_json_from(timeout=2)
        event2 = await comm2.receive_json_from(timeout=2)
        self.assertEqual(event1["order_id"], self.order.id)
        self.assertEqual(event2["order_id"], self.order.id)

        await comm1.disconnect()
        await comm2.disconnect()


# ---------------------------------------------------------------------------
# M3: publication semantics — commit/rollback/no-op/duplicate/rejected
# ---------------------------------------------------------------------------


class PublishSemanticsTests(RealtimeFixtureMixin, TestCase):
    def setUp(self):
        self._make_fixtures()
        self.order = self.make_order()

    def test_accept_commit_publishes_exactly_one_event(self):
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.accept(self.order.id, staff_user=None)
        self.assertEqual(mocked.call_count, 1)
        snapshot = mocked.call_args[0][0]
        self.assertEqual(snapshot.order_id, self.order.id)
        self.assertEqual(snapshot.status_orders, Orders.WAITING)
        self.assertEqual(snapshot.version, 1)

    def test_rollback_publishes_no_event(self):
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                try:
                    with transaction.atomic():
                        OrderStateService.accept(self.order.id, staff_user=None)
                        raise RuntimeError("boom")
                except RuntimeError:
                    pass
        self.assertEqual(mocked.call_count, 0)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status_orders, Orders.NEW)
        self.assertEqual(self.order.version, 0)

    def test_double_accept_is_noop_publishes_once_total(self):
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.accept(self.order.id, staff_user=None)
                OrderStateService.accept(self.order.id, staff_user=None)
        self.assertEqual(mocked.call_count, 1)

    def test_rejected_transition_publishes_no_event(self):
        OrderStateService.accept(self.order.id, staff_user=None)
        OrderStateService.payment_succeeded(self.order.id, provider="lifepay", provider_transaction_id="tx-0")
        OrderStateService.complete(self.order.id, staff_user=None)

        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(OrderTransitionError):
                    OrderStateService.accept(self.order.id, staff_user=None)
        self.assertEqual(mocked.call_count, 0)

    def test_payment_succeeded_combined_transition_publishes_one_event(self):
        OrderStateService.accept(self.order.id, staff_user=None)
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.payment_succeeded(
                    self.order.id, provider="lifepay", provider_transaction_id="tx-1"
                )
        self.assertEqual(mocked.call_count, 1)
        snapshot = mocked.call_args[0][0]
        self.assertEqual(snapshot.status_orders, Orders.IN_PROGRESS)
        self.assertEqual(snapshot.payment_status, Orders.PAID)

    def test_duplicate_webhook_publishes_exactly_one_event(self):
        OrderStateService.accept(self.order.id, staff_user=None)
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.payment_succeeded(
                    self.order.id, provider="lifepay", provider_transaction_id="tx-1", event_key="evt-1"
                )
                OrderStateService.payment_succeeded(
                    self.order.id, provider="lifepay", provider_transaction_id="tx-1", event_key="evt-1"
                )
        self.assertEqual(mocked.call_count, 1)

    def test_late_payment_after_cancel_does_not_publish(self):
        """M3 п.36: Late Payment не меняет status_orders => обычный order.status_changed не шлём."""
        OrderStateService.cancel(self.order.id, actor_type="customer")
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.payment_succeeded(
                    self.order.id, provider="lifepay", provider_transaction_id="tx-late"
                )
        self.assertEqual(mocked.call_count, 0)

    def test_cancel_publishes_one_event_with_reason(self):
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.cancel(self.order.id, actor_type="customer", reason="передумал")
        self.assertEqual(mocked.call_count, 1)
        snapshot = mocked.call_args[0][0]
        self.assertEqual(snapshot.status_orders, Orders.CANCELED)
        self.assertEqual(snapshot.cancellation_reason, "передумал")

    def test_complete_publishes_one_event(self):
        OrderStateService.accept(self.order.id, staff_user=None)
        OrderStateService.payment_succeeded(self.order.id, provider="lifepay", provider_transaction_id="tx-2")
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.complete(self.order.id, staff_user=None)
        self.assertEqual(mocked.call_count, 1)

    def test_payment_failed_publishes_one_event(self):
        OrderStateService.payment_started(self.order.id, provider="sbp")
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.payment_failed(self.order.id, provider="sbp", reason="declined")
        self.assertEqual(mocked.call_count, 1)

    def test_admin_override_status_change_publishes_one_event(self):
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.admin_override(
                    self.order.id,
                    admin_user=self.staff_user,
                    new_order_status=Orders.CANCELED,
                    reason="fraud",
                )
        self.assertEqual(mocked.call_count, 1)

    def test_admin_override_reason_only_does_not_publish(self):
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.admin_override(
                    self.order.id, admin_user=self.staff_user, reason="just an audit note"
                )
        self.assertEqual(mocked.call_count, 0)

    def test_event_payload_shape_has_no_pii(self):
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.accept(self.order.id, staff_user=None)
        payload = mocked.call_args[0][0].to_payload()
        self.assertEqual(payload["type"], "order.status_changed")
        self.assertEqual(payload["order_id"], self.order.id)
        self.assertIn("version", payload)
        self.assertIn("updated_at", payload)
        self.assertIn("status_orders", payload)
        self.assertIn("payment_status", payload)
        for pii_field in ("user_id", "phone_number", "email", "access_token", "coffee_shop_id"):
            self.assertNotIn(pii_field, payload)


# ---------------------------------------------------------------------------
# M2 п.57: реальный Redis (не InMemoryChannelLayer) — group_send -> receive
# ---------------------------------------------------------------------------


class RealRedisChannelLayerIntegrationTests(SimpleTestCase):
    """Единственный тест, который реально ходит в Redis через channels_redis —
    доказывает, что production CHANNEL_LAYERS-конфигурация действительно работает,
    а не только InMemoryChannelLayer, использованный во всех остальных тестах этого
    файла ради скорости/изоляции."""

    async def test_group_send_delivered_via_real_redis(self):
        from channels_redis.core import RedisChannelLayer
        from django.conf import settings

        redis_url = settings.CHANNEL_LAYERS["default"]["CONFIG"]["hosts"][0]
        layer = RedisChannelLayer(hosts=[redis_url])
        channel_name = await layer.new_channel()
        group = "orders.user.999999"
        await layer.group_add(group, channel_name)
        try:
            await layer.group_send(
                group, {"type": "order.status_changed", "payload": {"order_id": 1, "version": 1}}
            )
            message = await asyncio.wait_for(layer.receive(channel_name), timeout=5)
        finally:
            await layer.group_discard(group, channel_name)
            await layer.flush()

        self.assertEqual(message["type"], "order.status_changed")
        self.assertEqual(message["payload"]["order_id"], 1)
