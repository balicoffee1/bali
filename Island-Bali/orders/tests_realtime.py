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
    async def connect_and_read_snapshot(communicator):
        """
        M7: первый кадр после accept() — всегда order.snapshot (в т.ч. пустой).
        Тесты, которым интересны последующие события, обязаны его вычитать —
        иначе они прочитают снапшот вместо ожидаемого события.
        """
        connected, _ = await communicator.connect()
        if not connected:
            return False, None
        snapshot = await communicator.receive_json_from(timeout=2)
        # У сотрудника следом приходит полное состояние смены по каждой его
        # кофейне — тесты, которым интересны последующие события, обязаны его
        # вычитать, иначе прочитают снапшот вместо ожидаемой дельты.
        while not await communicator.receive_nothing(timeout=0.2):
            frame = await communicator.receive_json_from(timeout=1)
            if frame.get("type") != "orders.shop_snapshot":
                break
        return True, snapshot

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
        await self.connect_and_read_snapshot(communicator)
        await communicator.send_json_to({"type": "ping"})
        response = await communicator.receive_json_from(timeout=2)
        self.assertEqual(response, {"type": "pong"})
        await communicator.disconnect()

    async def test_unknown_frame_type_does_not_crash_connection(self):
        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.customer))
        )
        await self.connect_and_read_snapshot(communicator)
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
        await self.connect_and_read_snapshot(communicator)
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
        self.assertTrue((await self.connect_and_read_snapshot(comm_a))[0])
        self.assertTrue((await self.connect_and_read_snapshot(comm_b))[0])

        await database_sync_to_async(OrderStateService.accept)(self.order_a.id, staff_user=None)

        event = await comm_a.receive_json_from(timeout=2)
        self.assertEqual(event["audience"], "customer")
        self.assertEqual(event["order"]["id"], self.order_a.id)
        self.assertEqual(event["order"]["status_orders"], Orders.WAITING)

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
        self.assertTrue((await self.connect_and_read_snapshot(comm_staff_a))[0])
        self.assertTrue((await self.connect_and_read_snapshot(comm_staff_b))[0])

        await database_sync_to_async(OrderStateService.accept)(
            self.order_shop_a.id, staff_user=self.staff_user
        )
        event_a = await comm_staff_a.receive_json_from(timeout=2)
        self.assertEqual(event_a["audience"], "staff")
        self.assertEqual(event_a["order"]["id"], self.order_shop_a.id)
        self.assertTrue(await comm_staff_b.receive_nothing(timeout=0.5))

        await database_sync_to_async(OrderStateService.accept)(
            self.order_shop_b.id, staff_user=self.other_shop_staff_user
        )
        event_b = await comm_staff_b.receive_json_from(timeout=2)
        self.assertEqual(event_b["order"]["id"], self.order_shop_b.id)
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
        self.assertTrue((await self.connect_and_read_snapshot(comm1))[0])
        self.assertTrue((await self.connect_and_read_snapshot(comm2))[0])

        await database_sync_to_async(OrderStateService.accept)(self.order.id, staff_user=None)

        event1 = await comm1.receive_json_from(timeout=2)
        event2 = await comm2.receive_json_from(timeout=2)
        self.assertEqual(event1["order"]["id"], self.order.id)
        self.assertEqual(event2["order"]["id"], self.order.id)

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

    def test_late_payment_after_cancel_publishes_payment_status(self):
        """
        M7 меняет решение M3 п.36 ("late payment не публикуем, раз status_orders не изменился").

        Тогда это было безопасно: клиент всё равно перечитывал заказ по REST каждые
        5 секунд и рано или поздно видел payment_status=Paid. После отказа от polling'а
        неопубликованное изменение — это изменение, о котором клиент не узнает НИКОГДА:
        у отменённого заказа payment_status навсегда остался бы Pending/Failed, хотя
        деньги списаны (и именно по этому заказу заведена PaymentReconciliation).
        Инвариант теперь простой и проверяемый: version вырос => событие опубликовано.
        status_orders при этом не меняется — воскрешения отменённого заказа нет.
        """
        OrderStateService.cancel(self.order.id, actor_type="customer")
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.payment_succeeded(
                    self.order.id, provider="lifepay", provider_transaction_id="tx-late"
                )
        self.assertEqual(mocked.call_count, 1)
        snapshot = mocked.call_args[0][0]
        self.assertEqual(snapshot.payment_status, Orders.PAID)
        self.assertEqual(snapshot.status_orders, Orders.CANCELED)

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

    def test_customer_payload_shape_has_no_pii(self):
        """
        M7: payload стал полным заказом, поэтому проверка PII теперь про содержимое
        сериализатора, а не про короткий технический кадр. `user` в нём есть — это
        PK самого получателя, а не чужие данные; запрещены телефон/почта/токены и
        `login` (телефон клиента), который присутствует в staff-форме payload'а.
        """
        from orders.realtime import serialize_for_customer

        self.order.refresh_from_db()
        payload = serialize_for_customer(self.order)
        for field in ("status_orders", "payment_status", "version", "event_seq", "updated_at"):
            self.assertIn(field, payload)
        for pii_field in ("login", "phone_number", "email", "password", "access_token"):
            self.assertNotIn(pii_field, payload)


# ---------------------------------------------------------------------------
# M7 шаг 1: event_seq и публикация на всех мутациях, видимых клиенту
# ---------------------------------------------------------------------------


class EventSeqTests(RealtimeFixtureMixin, TestCase):
    """
    event_seq — версия ленты событий заказа, по которой клиент отбрасывает дубли
    и опоздавшие события. Инвариант: он растёт РОВНО тогда, когда публикуется
    событие. Отдельно от version, который остаётся версией бизнес-состояния и не
    двигается на presentation-изменениях.
    """

    def setUp(self):
        self._make_fixtures()
        self.order = self.make_order()

    def test_increments_on_every_published_event(self):
        with self.captureOnCommitCallbacks(execute=True):
            OrderStateService.accept(self.order.id, staff_user=None)
        self.order.refresh_from_db()
        self.assertEqual(self.order.event_seq, 1)

        with self.captureOnCommitCallbacks(execute=True):
            OrderStateService.payment_succeeded(
                self.order.id, provider="lifepay", provider_transaction_id="tx-1"
            )
        self.order.refresh_from_db()
        self.assertEqual(self.order.event_seq, 2)

    def test_not_bumped_when_nothing_published(self):
        with self.captureOnCommitCallbacks(execute=True):
            OrderStateService.accept(self.order.id, staff_user=None)
            OrderStateService.accept(self.order.id, staff_user=None)  # повторный тап — no-op
        self.order.refresh_from_db()
        self.assertEqual(self.order.event_seq, 1)

    def test_rollback_does_not_bump(self):
        try:
            with transaction.atomic():
                OrderStateService.accept(self.order.id, staff_user=None)
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        self.order.refresh_from_db()
        self.assertEqual(self.order.event_seq, 0)

    def test_snapshot_descriptor_carries_event_seq(self):
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.accept(self.order.id, staff_user=None)
        descriptor = mocked.call_args[0][0]
        self.assertEqual(descriptor.event_seq, 1)
        self.assertEqual(descriptor.version, 1)

    def test_presentation_change_bumps_event_seq_but_not_version(self):
        """Ключевое различие двух счётчиков — иначе клиент выбросил бы это событие."""
        from django.utils import timezone

        with self.captureOnCommitCallbacks(execute=True):
            OrderStateService.update_presentation(
                self.order.id, actor_type="staff", updated_time=timezone.now() + timedelta(minutes=5)
            )
        self.order.refresh_from_db()
        self.assertEqual(self.order.event_seq, 1)
        self.assertEqual(self.order.version, 0)


class MissingPublicationTests(RealtimeFixtureMixin, TestCase):
    """
    M7, раздел 2.2: мутации, которые раньше не публиковали событий вовсе и работали
    только потому, что клиент перечитывал заказ каждые 5 секунд. После отказа от
    polling'а каждая из них — это диалог, который иначе не откроется/не закроется.
    """

    def setUp(self):
        self._make_fixtures()
        self.order = self.make_order()

    def test_order_created_publishes_without_version_bump(self):
        """Создание — не переход state machine, но диалог «ожидание подтверждения»
        открывается именно по нему."""
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.order_created(self.order.id)
        self.assertEqual(mocked.call_count, 1)
        snapshot = mocked.call_args[0][0]
        self.assertEqual(snapshot.status_orders, Orders.NEW)
        self.assertEqual(snapshot.version, 0)
        self.assertEqual(snapshot.event_seq, 1)

    def test_client_confirmed_publishes(self):
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.client_confirmed(self.order.id, user=self.customer)
        self.assertEqual(mocked.call_count, 1)

    def test_client_confirmed_twice_publishes_once(self):
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.client_confirmed(self.order.id, user=self.customer)
                OrderStateService.client_confirmed(self.order.id, user=self.customer)
        self.assertEqual(mocked.call_count, 1)

    def test_updated_time_publishes(self):
        from django.utils import timezone

        new_time = timezone.now() + timedelta(minutes=7)
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.update_presentation(
                    self.order.id, actor_type="staff", updated_time=new_time
                )
        self.assertEqual(mocked.call_count, 1)
        self.order.refresh_from_db()
        self.assertEqual(self.order.updated_time, new_time)

    def test_is_appreciated_publishes(self):
        """Оценка заказа гасит диалог «оцените заказ» — клиент обязан узнать событием."""
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.update_presentation(
                    self.order.id, actor_type="customer", is_appreciated=True
                )
        self.assertEqual(mocked.call_count, 1)

    def test_update_presentation_is_idempotent(self):
        """Запись того же значения — не изменение, значит и не событие."""
        from django.utils import timezone

        new_time = timezone.now() + timedelta(minutes=7)
        with self.captureOnCommitCallbacks(execute=True):
            OrderStateService.update_presentation(
                self.order.id, actor_type="staff", updated_time=new_time
            )
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.update_presentation(
                    self.order.id, actor_type="staff", updated_time=new_time
                )
        self.assertEqual(mocked.call_count, 0)

    def test_update_presentation_rejects_state_machine_fields(self):
        """PRESENTATION_FIELDS — ещё и граница против mass-assignment статуса."""
        for field, value in (
            ("status_orders", Orders.COMPLETED),
            ("payment_status", Orders.PAID),
            ("version", 99),
        ):
            with self.subTest(field=field):
                with self.assertRaises(OrderTransitionError) as ctx:
                    OrderStateService.update_presentation(
                        self.order.id, actor_type="staff", **{field: value}
                    )
                self.assertEqual(ctx.exception.code, "invalid_presentation_field")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status_orders, Orders.NEW)
        self.assertEqual(self.order.version, 0)

    def test_staff_serializer_time_change_publishes(self):
        """
        Путь, которым бариста реально меняет время (staff/views.py -> PatchOrderSerializer).
        Раньше он писал updated_time голым instance.save() мимо сервиса — событие не
        уходило, и диалог «время изменено» появлялся только на следующем тике polling'а.
        """
        from django.utils import timezone

        from staff.serializers import PatchOrderSerializer

        new_time = timezone.now() + timedelta(minutes=9)
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                PatchOrderSerializer().update_order(
                    self.order, {"new_time_to_finish": new_time, "new_comments": "занят"}
                )
        self.assertEqual(mocked.call_count, 1)
        self.order.refresh_from_db()
        self.assertEqual(self.order.updated_time, new_time)
        self.assertEqual(self.order.cancellation_reason, "занят")


# ---------------------------------------------------------------------------
# M7 шаг 2: снапшот на коннекте + полный payload + маркер аудитории
# ---------------------------------------------------------------------------


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYERS)
class ConnectSnapshotTests(RealtimeFixtureMixin, TransactionTestCase):
    """
    Снапшот на коннекте — это замена холодного REST-запроса: ради него клиент и
    подключается («подключился и сразу видит свой последний заказ»).
    """

    def setUp(self):
        self._make_fixtures()

    async def test_snapshot_contains_latest_order(self):
        older = await database_sync_to_async(self.make_order)()
        newer = await database_sync_to_async(self.make_order)()

        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.customer))
        )
        connected, snapshot = await self.connect_and_read_snapshot(communicator)
        self.assertTrue(connected)

        self.assertEqual(snapshot["type"], "order.snapshot")
        self.assertEqual(snapshot["audience"], "customer")
        self.assertEqual(len(snapshot["orders"]), 1)
        # именно последний, а не произвольная строка: весь клиентский UI читает
        # "мой последний заказ", и порядок строк Postgres не гарантирует
        self.assertEqual(snapshot["orders"][0]["id"], newer.id)
        self.assertNotEqual(snapshot["orders"][0]["id"], older.id)
        await communicator.disconnect()

    async def test_snapshot_is_empty_list_for_user_without_orders(self):
        """Пустой снапшот обязателен: без него клиент не отличит «ещё грузится»
        от «заказов нет» и зависнет в спиннере."""
        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.other_customer))
        )
        connected, snapshot = await self.connect_and_read_snapshot(communicator)
        self.assertTrue(connected)
        self.assertEqual(snapshot["type"], "order.snapshot")
        self.assertEqual(snapshot["orders"], [])
        await communicator.disconnect()

    async def test_snapshot_never_contains_another_users_order(self):
        await database_sync_to_async(self.make_order)(user=self.customer)

        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.other_customer))
        )
        connected, snapshot = await self.connect_and_read_snapshot(communicator)
        self.assertTrue(connected)
        self.assertEqual(snapshot["orders"], [])
        await communicator.disconnect()

    async def test_snapshot_carries_fields_the_dialogs_depend_on(self):
        """Если хоть одно из этих полей не доедет, соответствующий диалог сломается."""
        order = await database_sync_to_async(self.make_order)()

        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.customer))
        )
        _connected, snapshot = await self.connect_and_read_snapshot(communicator)
        payload = snapshot["orders"][0]
        for field in (
            "status_orders", "payment_status", "updated_time", "client_confirmed",
            "is_appreciated", "cancellation_reason", "coffee_shop_name", "time_is_finish",
            "created_at", "version", "event_seq",
        ):
            self.assertIn(field, payload, f"диалоги зависят от {field}")
        self.assertEqual(payload["id"], order.id)
        await communicator.disconnect()


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYERS)
class AudienceRoutingTests(RealtimeFixtureMixin, TransactionTestCase):
    """
    Мобильное приложение у покупателя и у бариста — одно и то же, и staff-соединение
    подписано сразу на две группы. Без маркера audience customer-слой применил бы
    чужой заказ, прилетевший по shop-группе, как «мой последний заказ».
    """

    def setUp(self):
        self._make_fixtures()

    async def test_staff_who_is_also_customer_gets_both_frames_distinguishable(self):
        # заказ самого staff-пользователя в его же кофейне: событие уйдёт и в его
        # user-группу, и в shop-группу его смены — по одному соединению придут оба
        cart = await database_sync_to_async(ShoppingCart.objects.create)(
            user=self.staff_user, is_active=True
        )
        order = await database_sync_to_async(self.make_order)(
            user=self.staff_user, cart=cart, coffee_shop=self.coffee_shop
        )

        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.staff_user))
        )
        self.assertTrue((await self.connect_and_read_snapshot(communicator))[0])

        await database_sync_to_async(OrderStateService.accept)(order.id, staff_user=self.staff_user)

        first = await communicator.receive_json_from(timeout=2)
        second = await communicator.receive_json_from(timeout=2)
        audiences = sorted([first["audience"], second["audience"]])
        self.assertEqual(audiences, ["customer", "staff"])

        by_audience = {frame["audience"]: frame for frame in (first, second)}
        # customer-форма — без телефона клиента, staff-форма — с ним и с составом корзины
        self.assertNotIn("login", by_audience["customer"]["order"])
        self.assertIn("login", by_audience["staff"]["order"])
        self.assertIn("cart", by_audience["staff"]["order"])
        await communicator.disconnect()


class PayloadParityTests(RealtimeFixtureMixin, TestCase):
    def setUp(self):
        self._make_fixtures()
        self.order = self.make_order()

    def test_ws_payload_matches_rest_fields_except_cart_data(self):
        """
        Регресс-тест на расхождение WS и REST: мобильный OrderView.fromJson —
        единственный парсер на обе стороны, поэтому набор полей обязан совпадать.
        cart_data — единственное осознанное исключение (тяжёлый вложенный
        сериализатор, который клиент не читает).
        """
        from orders.serializers import OrderRealtimeSerializer, OrderSerializers

        rest_fields = set(OrderSerializers().fields.keys())
        ws_fields = set(OrderRealtimeSerializer().fields.keys())
        self.assertEqual(rest_fields - ws_fields, {"cart_data"})
        self.assertEqual(ws_fields - rest_fields, set())

    def test_staff_payload_carries_event_seq(self):
        """Дедупликация событий на staff-экране такая же, как на клиентском."""
        from orders.realtime import serialize_for_staff

        payload = serialize_for_staff(self.order)
        self.assertIn("event_seq", payload)
        self.assertIn("version", payload)


# ---------------------------------------------------------------------------
# M7: экран смены целиком на WebSocket
# ---------------------------------------------------------------------------


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYERS)
class ShopSnapshotTests(RealtimeFixtureMixin, TransactionTestCase):
    """
    Сотруднику при подключении приходит полное состояние смены — то, за чем
    экран раньше ходил четырьмя HTTP-запросами каждые 30 секунд.
    """

    def setUp(self):
        self._make_fixtures()

    async def _connect(self, user):
        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(user))
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        frames = []
        # первый кадр — покупательский снапшот, дальше состояния смен
        while not await communicator.receive_nothing(timeout=0.3):
            frames.append(await communicator.receive_json_from(timeout=1))
        return communicator, frames

    async def test_staff_receives_shop_snapshot_on_connect(self):
        await database_sync_to_async(self.make_order)(
            coffee_shop=self.coffee_shop, status_orders=Orders.WAITING
        )
        communicator, frames = await self._connect(self.staff_user)

        shop_frames = [f for f in frames if f["type"] == "orders.shop_snapshot"]
        self.assertEqual(len(shop_frames), 1)
        snapshot = shop_frames[0]
        self.assertEqual(snapshot["audience"], "staff")
        self.assertEqual(snapshot["coffee_shop_id"], self.coffee_shop.id)
        for key in ("orders", "columns", "status_counts", "payment_totals",
                    "order_totals", "shift_window_minutes"):
            self.assertIn(key, snapshot)
        self.assertEqual(
            sorted(snapshot["columns"]), ["Completed", "In Progress", "Waiting"]
        )
        await communicator.disconnect()

    async def test_plain_customer_gets_no_shop_snapshot(self):
        communicator, frames = await self._connect(self.customer)
        self.assertEqual([f["type"] for f in frames], ["order.snapshot"])
        await communicator.disconnect()

    async def test_snapshot_columns_contain_only_this_shop(self):
        mine = await database_sync_to_async(self.make_order)(
            coffee_shop=self.coffee_shop, status_orders=Orders.WAITING
        )
        other_cart = await database_sync_to_async(ShoppingCart.objects.create)(
            user=self.other_customer, is_active=True
        )
        await database_sync_to_async(self.make_order)(
            coffee_shop=self.other_shop, cart=other_cart, status_orders=Orders.WAITING
        )

        communicator, frames = await self._connect(self.staff_user)
        snapshot = next(f for f in frames if f["type"] == "orders.shop_snapshot")
        waiting_ids = [order["id"] for order in snapshot["columns"]["Waiting"]]
        self.assertEqual(waiting_ids, [mine.id])
        await communicator.disconnect()

    async def test_snapshot_can_be_requested_mid_session(self):
        """Экран смены могли открыть, когда соединение уже давно установлено."""
        communicator, _frames = await self._connect(self.staff_user)

        await communicator.send_json_to({"type": "shop_snapshot_request"})
        frame = await communicator.receive_json_from(timeout=2)
        self.assertEqual(frame["type"], "orders.shop_snapshot")
        self.assertEqual(frame["coffee_shop_id"], self.coffee_shop.id)
        await communicator.disconnect()

    async def test_snapshot_request_from_customer_returns_nothing(self):
        """Подписки на кофейни у покупателя нет — и запросить её нельзя."""
        communicator, _frames = await self._connect(self.customer)

        await communicator.send_json_to({"type": "shop_snapshot_request"})
        self.assertTrue(await communicator.receive_nothing(timeout=0.5))
        await communicator.disconnect()

    async def test_staff_delta_carries_coffee_shop_id(self):
        """Сотрудник может работать в двух точках — экран должен взять свою."""
        order = await database_sync_to_async(self.make_order)(
            coffee_shop=self.coffee_shop, status_orders=Orders.NEW
        )
        communicator, _frames = await self._connect(self.staff_user)

        await database_sync_to_async(OrderStateService.accept)(
            order.id, staff_user=self.staff_user
        )
        frames = []
        while not await communicator.receive_nothing(timeout=0.3):
            frames.append(await communicator.receive_json_from(timeout=1))

        staff_frame = next(f for f in frames if f.get("audience") == "staff")
        self.assertEqual(staff_frame["coffee_shop_id"], self.coffee_shop.id)
        self.assertIn("status_counts", staff_frame)
        self.assertEqual(staff_frame["order"]["status_orders"], Orders.WAITING)
        await communicator.disconnect()

    async def test_staff_of_two_shops_gets_a_snapshot_for_each(self):
        await database_sync_to_async(Staff.objects.create)(
            users=self.staff_user, place_of_work=self.other_shop
        )
        communicator, frames = await self._connect(self.staff_user)
        shop_ids = sorted(
            f["coffee_shop_id"] for f in frames if f["type"] == "orders.shop_snapshot"
        )
        self.assertEqual(shop_ids, sorted([self.coffee_shop.id, self.other_shop.id]))
        await communicator.disconnect()


class ShopStateParityTests(RealtimeFixtureMixin, TestCase):
    """
    Состав колонок обязан совпадать с тем, что отдаёт REST: обе стороны собраны
    из одних функций (staff/queries.py), и этот тест сторожит, чтобы кто-нибудь
    не начал считать «что видно на экране» отдельно для WebSocket.
    """

    def setUp(self):
        self._make_fixtures()

    def test_columns_match_rest_querysets(self):
        from orders.realtime import shop_snapshot_payload
        from staff.queries import orders_with_status

        for status in (Orders.WAITING, Orders.IN_PROGRESS, Orders.COMPLETED):
            self.make_order(coffee_shop=self.coffee_shop, status_orders=status)

        payload = shop_snapshot_payload(self.coffee_shop.id)
        for status in (Orders.WAITING, Orders.IN_PROGRESS, Orders.COMPLETED):
            expected = list(
                orders_with_status(
                    city_id=None, coffee_shop_id=self.coffee_shop.id, status=status
                ).values_list("id", flat=True)
            )
            self.assertEqual(
                [order["id"] for order in payload["columns"][status]], expected
            )

    def test_staff_delta_carries_aggregates(self):
        """
        Счётчики карточки смены считаются по всей таблице, из колонок их не
        вывести — поэтому они едут с каждой дельтой, иначе застыли бы на
        значениях момента подключения.
        """
        from orders.realtime import serialize_for_staff

        order = self.make_order()
        payload = {
            "type": "order.status_changed",
            "audience": "staff",
            "order": serialize_for_staff(order),
        }
        from staff.queries import shift_aggregates

        payload.update(shift_aggregates())
        for key in ("status_counts", "payment_totals", "order_totals"):
            self.assertIn(key, payload)

    def test_aggregates_are_json_serializable(self):
        """Channels сериализует обычным json.dumps — Decimal там падает."""
        import json

        from staff.queries import shift_aggregates

        self.make_order()
        json.dumps(shift_aggregates())  # не должно бросать


class ConnectionStaysAliveTests(RealtimeFixtureMixin, TransactionTestCase):
    """
    M7 (регресс с живого стенда): сервер принимал соединение, отправлял снапшот
    и через секунду закрывал его с кодом 1011 — то есть падал уже после accept.
    Клиент переподключался, получал снапшот, снова терял соединение, и так по
    кругу раз в две секунды.

    Тесты выше проверяли только «подключились и сразу отключились» и такой отказ
    поймать не могли. Здесь соединение специально держат несколько секунд и
    проверяют пингом, что оно живо.

    Канальный слой намеренно НЕ подменяется на InMemory: разница между ним и
    настоящим Redis — первое, на что падает подозрение при 1011.
    """
    def setUp(self):
        self._make_fixtures()

    async def test_customer_connection_survives_after_snapshot(self):
        await database_sync_to_async(self.make_order)()
        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.customer))
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        snapshot = await communicator.receive_json_from(timeout=3)
        self.assertEqual(snapshot["type"], "order.snapshot")

        # Ровно то, что происходит в проде: клиент молчит, а сервер через
        # ~1 секунду закрывает соединение с 1011.
        await asyncio.sleep(3)
        self.assertTrue(
            await communicator.receive_nothing(timeout=1),
            "соединение прислало что-то неожиданное",
        )
        await communicator.send_json_to({"type": "ping"})
        pong = await communicator.receive_json_from(timeout=3)
        self.assertEqual(pong, {"type": "pong"}, "соединение мертво")
        await communicator.disconnect()

    async def test_staff_connection_survives_after_snapshot(self):
        communicator = WebsocketCommunicator(
            application, "/ws/orders/", headers=self.auth_headers(self.token_for(self.staff_user))
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        while not await communicator.receive_nothing(timeout=0.5):
            await communicator.receive_json_from(timeout=2)

        await asyncio.sleep(3)
        await communicator.send_json_to({"type": "ping"})
        pong = await communicator.receive_json_from(timeout=3)
        self.assertEqual(pong, {"type": "pong"}, "соединение мертво")
        await communicator.disconnect()


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
