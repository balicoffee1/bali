"""
M1: тесты OrderStateService / state machine / payment deadline-grace /
конкурентности / авторизации / платёжной безопасности.

Полный набор (включая DefaultOrderEndpointMassAssignmentTests, см. ниже)
реально прогнан через `docker compose exec web python manage.py test
--noinput` в штатном docker-compose окружении проекта: 75/75 passed.
"""
import threading
import time
from datetime import timedelta
from decimal import Decimal
from unittest import mock
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from acquiring.providers import ProviderPaymentStatus
from acquiring.models import LifepayInvoice
from cart.models import ShoppingCart
from coffee_shop.models import Acquiring, City, CoffeeShop, CrmSystem
from orders.models import OrderDialogAck, Orders, PaymentReconciliation, PaymentWebhookEvent
from orders.services import OrderStateService
from orders.state_machine import (
    FINAL_DEADLINE_SECONDS,
    GRACE_PERIOD_SECONDS,
    PAYMENT_WINDOW_SECONDS,
    OrderTransitionError,
    is_order_transition_allowed,
    is_payment_transition_allowed,
)
from staff.models import Staff
from users.models import CustomUser


def make_coffee_shop(city):
    crm = CrmSystem.objects.create(name="QuickRestoApi")
    acquiring = Acquiring.objects.create(
        for_coffeeshop="Test", name="RussianStandart", login="login", password="password"
    )
    return CoffeeShop.objects.create(
        city=city,
        street="Arbat",
        building_number="1",
        email="shop@test.com",
        telegram_username="@test",
        crm_system=crm,
        acquiring=acquiring,
        lifepay_api_key="test-key",
        lifepay_login="test-login",
    )


class OrdersTestBase(TestCase):
    """Общий набор фикстур: пользователь, кофейня, заказ."""

    def setUp(self):
        self.city = City.objects.create(name="Moscow")
        self.coffee_shop = make_coffee_shop(self.city)
        self.user = CustomUser.objects.create_user(login='+79990000001', password='password123')
        self.other_user = CustomUser.objects.create_user(login='+79990000002', password='password123')
        self.staff_user = CustomUser.objects.create_user(login='+79990000003', password='password123')
        self.other_shop_staff_user = CustomUser.objects.create_user(login='+79990000004', password='password123')

        self.staff = Staff.objects.create(users=self.staff_user, place_of_work=self.coffee_shop)

        other_shop = make_coffee_shop(City.objects.create(name="Kazan"))
        self.other_shop_staff = Staff.objects.create(users=self.other_shop_staff_user, place_of_work=other_shop)

        self.cart = ShoppingCart.objects.create(user=self.user, is_active=True)

    def make_order(self, **overrides):
        defaults = dict(
            user=self.user,
            city_choose=self.city,
            coffee_shop=self.coffee_shop,
            cart=self.cart,
            full_price=Decimal('300.00'),
        )
        defaults.update(overrides)
        return Orders.objects.create(**defaults)

    def auth(self, client, user):
        refresh = RefreshToken.for_user(user)
        client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'


# ---------------------------------------------------------------------------
# 1. State machine: разрешённые/запрещённые переходы
# ---------------------------------------------------------------------------

class OrderStateMachineTransitionTests(TestCase):
    """Чистые проверки таблицы переходов (без БД) + 4 явно запрещённых сценария."""

    def test_new_to_waiting_allowed(self):
        self.assertTrue(is_order_transition_allowed(Orders.NEW, Orders.WAITING))

    def test_waiting_to_in_progress_allowed(self):
        self.assertTrue(is_order_transition_allowed(Orders.WAITING, Orders.IN_PROGRESS))

    def test_in_progress_to_completed_allowed(self):
        self.assertTrue(is_order_transition_allowed(Orders.IN_PROGRESS, Orders.COMPLETED))

    # --- 4 явно запрещённых перехода (см. "главный acceptance invariant" ТЗ) ---

    def test_forbidden_completed_to_waiting(self):
        """Сценарий 1 из acceptance invariant: поздний запрос не может откатить COMPLETED -> WAITING."""
        self.assertFalse(is_order_transition_allowed(Orders.COMPLETED, Orders.WAITING))

    def test_forbidden_canceled_to_in_progress(self):
        """Сценарий 2: поздний webhook не может воскресить CANCELED -> IN_PROGRESS."""
        self.assertFalse(is_order_transition_allowed(Orders.CANCELED, Orders.IN_PROGRESS))

    def test_forbidden_completed_to_canceled(self):
        """Уже выданный заказ нельзя отменить."""
        self.assertFalse(is_order_transition_allowed(Orders.COMPLETED, Orders.CANCELED))

    def test_forbidden_in_progress_to_new(self):
        """Нет обратных переходов вне терминальных состояний."""
        self.assertFalse(is_order_transition_allowed(Orders.IN_PROGRESS, Orders.NEW))

    def test_payment_paid_is_terminal(self):
        self.assertFalse(is_payment_transition_allowed(Orders.PAID, Orders.FAILED))
        self.assertFalse(is_payment_transition_allowed(Orders.PAID, Orders.PENDING))

    def test_payment_failed_is_terminal(self):
        self.assertFalse(is_payment_transition_allowed(Orders.FAILED, Orders.PAID))


class OrderStateServiceTransitionTests(OrdersTestBase):
    """OrderStateService поверх реальных объектов Orders."""

    def test_accept_waiting_from_new(self):
        order = self.make_order(status_orders=Orders.NEW)
        updated = OrderStateService.accept(order.id, staff_user=self.staff_user)
        self.assertEqual(updated.status_orders, Orders.WAITING)
        self.assertEqual(updated.version, 1)

    def test_accept_is_idempotent_on_double_call(self):
        order = self.make_order(status_orders=Orders.NEW)
        OrderStateService.accept(order.id, staff_user=self.staff_user)
        again = OrderStateService.accept(order.id, staff_user=self.staff_user)
        self.assertEqual(again.status_orders, Orders.WAITING)
        self.assertEqual(again.version, 1, "повторный accept() не должен увеличивать version повторно")

    def test_accept_completed_order_raises(self):
        order = self.make_order(status_orders=Orders.COMPLETED)
        with self.assertRaises(OrderTransitionError):
            OrderStateService.accept(order.id, staff_user=self.staff_user)

    def test_cancel_canceled_order_is_noop(self):
        order = self.make_order(status_orders=Orders.CANCELED)
        result = OrderStateService.cancel(order.id, actor_type="customer", reason="test")
        self.assertEqual(result.version, 0, "повторная отмена — no-op, version не растёт")

    def test_cancel_completed_order_raises(self):
        order = self.make_order(status_orders=Orders.COMPLETED)
        with self.assertRaises(OrderTransitionError):
            OrderStateService.cancel(order.id, actor_type="customer", reason="test")

    def test_cancel_does_not_acknowledge_the_cancellation_dialog(self):
        """
        Отмена заказа не должна считаться «клиент уже увидел диалог отмены».

        Раньше это стерегли через булево поле isOrderCancelled, имя которого
        читалось как «заказ отменён» — и сервис, честно выставляя его при отмене,
        гасил диалог до показа. Поле заменено на OrderDialogAck, но сам инвариант
        остаётся: подтверждение пишет только приложение и только после показа.
        """
        order = self.make_order(status_orders=Orders.NEW)
        updated = OrderStateService.cancel(order.id, actor_type="system", reason="payment timeout")
        self.assertEqual(updated.status_orders, Orders.CANCELED)
        self.assertFalse(
            OrderDialogAck.objects.filter(order=order, dialog_key=OrderDialogAck.CANCELED).exists(),
            "подтверждение диалога отмены пишет клиент после показа, а не сервис",
        )

    def test_system_cancel_never_cancels_paid_order(self):
        """Сценарий 3 acceptance invariant: Celery-таймаут не может отменить уже PAID заказ."""
        order = self.make_order(status_orders=Orders.IN_PROGRESS, payment_status=Orders.PAID)
        result = OrderStateService.cancel(order.id, actor_type="system", reason="timeout")
        order.refresh_from_db()
        self.assertEqual(order.status_orders, Orders.IN_PROGRESS)
        self.assertEqual(result.status_orders, Orders.IN_PROGRESS)

    def test_complete_requires_in_progress(self):
        order = self.make_order(status_orders=Orders.WAITING)
        with self.assertRaises(OrderTransitionError):
            OrderStateService.complete(order.id, staff_user=self.staff_user)

    def test_complete_deactivates_cart(self):
        order = self.make_order(status_orders=Orders.IN_PROGRESS)
        OrderStateService.complete(order.id, staff_user=self.staff_user)
        self.cart.refresh_from_db()
        self.assertFalse(self.cart.is_active)

    def test_version_does_not_increment_on_noop(self):
        order = self.make_order(status_orders=Orders.COMPLETED)
        v_before = order.version
        with self.assertRaises(OrderTransitionError):
            OrderStateService.cancel(order.id, actor_type="system", reason="ignored")  # уже terminal -> raises
        # cancel() на COMPLETED поднимает исключение до записи, version не тронут
        order.refresh_from_db()
        self.assertEqual(order.version, v_before)


# ---------------------------------------------------------------------------
# 2. Payment deadline / grace — 8 граничных сценариев
# ---------------------------------------------------------------------------

def _status(normalized, paid_at=None, code=None):
    return ProviderPaymentStatus(normalized_status=normalized, provider_paid_at=paid_at, raw_status_code=code)


class PaymentDeadlineGraceBoundaryTests(OrdersTestBase):
    """
    payment_window = 90s, grace = 30s, итоговый дедлайн = 120s.

    В проде момент "T0+90s"/"T0+120s" — это реальный Celery countdown
    (apply_async(countdown=90|120), см. orders/signals.py). Здесь мы не ждём
    90 секунд в тесте, а вызываем OrderStateService.evaluate_payment_deadline/
    finalize_payment_window напрямую, как это делает orders/tasks.py в момент
    срабатывания таска — эти методы сами по себе НЕ читают
    payment_deadline_at (это делает только payment_started(), см.
    test_payment_started_rejects_after_deadline ниже), они полагаются на то,
    что их вызвали в нужный момент. payment_started_at в фикстурах ниже
    используется только там, где он влияет на ветвление (Case A: платёж не
    начат вовсе).
    """

    def _order_at_t0(self, **overrides):
        now = timezone.now()
        order = self.make_order(
            status_orders=Orders.WAITING,
            payment_status=Orders.NEW,
            payment_deadline_at=now - timedelta(seconds=1),  # дедлайн уже наступил к моменту проверки
            **overrides,
        )
        return order

    # a) Оплата подтверждена задолго до дедлайна — таймаут не должен ничего трогать.
    def test_a_paid_well_before_deadline_untouched_by_timeout(self):
        order = self.make_order(status_orders=Orders.IN_PROGRESS, payment_status=Orders.PAID)
        OrderStateService.evaluate_payment_deadline(order.id, provider_status_checker=lambda o: _status("PAID"))
        order.refresh_from_db()
        self.assertEqual(order.status_orders, Orders.IN_PROGRESS)
        self.assertEqual(order.payment_status, Orders.PAID)

    # b) Оплата не была начата вовсе -> Case A: auto-cancel на T0+90s.
    def test_b_never_started_payment_autocancels_at_90s(self):
        order = self._order_at_t0(payment_started_at=None)
        OrderStateService.evaluate_payment_deadline(order.id, provider_status_checker=lambda o: _status("NOT_FOUND"))
        order.refresh_from_db()
        self.assertEqual(order.status_orders, Orders.CANCELED)

    # c) Оплата начата, провайдер всё ещё PENDING на T0+90s -> не отменяем, ждём grace.
    def test_c_pending_at_90s_does_not_cancel(self):
        order = self._order_at_t0(payment_started_at=timezone.now() - timedelta(seconds=91))
        OrderStateService.evaluate_payment_deadline(order.id, provider_status_checker=lambda o: _status("PENDING"))
        order.refresh_from_db()
        self.assertNotEqual(order.status_orders, Orders.CANCELED)
        self.assertEqual(order.payment_status, Orders.NEW)

    # d) Провайдер подтверждает PAID ровно в момент проверки T0+90s -> payment_succeeded, без отмены.
    def test_d_provider_confirms_paid_exactly_at_90s(self):
        order = self._order_at_t0(payment_started_at=timezone.now() - timedelta(seconds=91))
        paid_at = timezone.now()
        OrderStateService.evaluate_payment_deadline(
            order.id, provider_status_checker=lambda o: _status("PAID", paid_at=paid_at, code=10)
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Orders.PAID)
        self.assertEqual(order.status_orders, Orders.IN_PROGRESS)

    # e) Всё ещё PENDING на T0+120s (конец grace) -> finalize отменяет.
    def test_e_still_pending_at_120s_cancels(self):
        order = self._order_at_t0(payment_started_at=timezone.now() - timedelta(seconds=121))
        OrderStateService.finalize_payment_window(order.id, provider_status_checker=lambda o: _status("PENDING"))
        order.refresh_from_db()
        self.assertEqual(order.status_orders, Orders.CANCELED)
        self.assertEqual(order.payment_status, Orders.FAILED)

    # f) Провайдер подтверждает PAID ровно в момент проверки T0+120s -> PAID побеждает.
    def test_f_provider_confirms_paid_exactly_at_120s(self):
        order = self._order_at_t0(payment_started_at=timezone.now() - timedelta(seconds=121))
        OrderStateService.finalize_payment_window(
            order.id, provider_status_checker=lambda o: _status("PAID", paid_at=timezone.now(), code=10)
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Orders.PAID)
        self.assertNotEqual(order.status_orders, Orders.CANCELED)

    # g) Поздний платёж после того, как заказ уже CANCELED -> реконсиляция, БЕЗ воскрешения.
    def test_g_late_payment_after_cancel_creates_reconciliation_not_resurrect(self):
        order = self.make_order(status_orders=Orders.CANCELED, payment_status=Orders.FAILED)
        OrderStateService.payment_succeeded(
            order.id, provider="lifepay", provider_transaction_id="tx-1", event_key="tx-1:10"
        )
        order.refresh_from_db()
        self.assertEqual(order.status_orders, Orders.CANCELED, "CANCELED не должен воскресать")
        self.assertEqual(order.payment_status, Orders.PAID, "payment_status всё равно фиксирует факт оплаты")
        self.assertEqual(PaymentReconciliation.objects.filter(order=order).count(), 1)
        reconciliation = PaymentReconciliation.objects.get(order=order)
        self.assertEqual(reconciliation.status, PaymentReconciliation.LATE_PAYMENT)

    # h) PAID, зафиксированный конкурентно ДО прихода таймаут-таска, побеждает над авто-отменой.
    def test_h_paid_before_timeout_task_beats_autocancel(self):
        order = self._order_at_t0(payment_started_at=timezone.now() - timedelta(seconds=91))
        OrderStateService.payment_succeeded(order.id, provider="lifepay", provider_transaction_id="tx-2", event_key="tx-2:10")
        # Таймаут-таск "опаздывает" и всё равно исполняется после payment_succeeded:
        OrderStateService.evaluate_payment_deadline(order.id, provider_status_checker=lambda o: _status("FAILED"))
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Orders.PAID)
        self.assertNotEqual(order.status_orders, Orders.CANCELED)

    def test_payment_window_constants_match_tz(self):
        self.assertEqual(PAYMENT_WINDOW_SECONDS, 90)
        self.assertEqual(GRACE_PERIOD_SECONDS, 30)
        self.assertEqual(FINAL_DEADLINE_SECONDS, 120)

    # i) payment_started() сам проверяет payment_deadline_at (в отличие от
    # evaluate_payment_deadline/finalize_payment_window) — новая попытка
    # оплаты после дедлайна должна быть отклонена backend'ом, а не только UI.
    def test_i_payment_started_rejects_after_deadline(self):
        order = self.make_order(
            status_orders=Orders.WAITING,
            payment_status=Orders.NEW,
            payment_deadline_at=timezone.now() - timedelta(seconds=1),
        )
        with self.assertRaises(OrderTransitionError) as ctx:
            OrderStateService.payment_started(order.id, provider="lifepay")
        self.assertEqual(ctx.exception.code, "payment_window_closed")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Orders.NEW)


# ---------------------------------------------------------------------------
# 3. Идемпотентность webhook-событий
# ---------------------------------------------------------------------------

class WebhookIdempotencyTests(OrdersTestBase):
    def test_duplicate_event_key_processed_once(self):
        order = self.make_order(status_orders=Orders.WAITING, payment_status=Orders.NEW)
        OrderStateService.payment_succeeded(order.id, provider="lifepay", provider_transaction_id="tx-3", event_key="tx-3:10")
        order.refresh_from_db()
        self.assertEqual(order.version, 1)

        # Повторная доставка того же события (тот же event_key) — no-op.
        OrderStateService.payment_succeeded(order.id, provider="lifepay", provider_transaction_id="tx-3", event_key="tx-3:10")
        order.refresh_from_db()
        self.assertEqual(order.version, 1, "повторный webhook не должен увеличивать version повторно")
        self.assertEqual(PaymentWebhookEvent.objects.filter(order=order).count(), 1)

    def test_different_status_code_is_a_new_event(self):
        order = self.make_order(status_orders=Orders.WAITING, payment_status=Orders.NEW)
        OrderStateService.payment_failed(order.id, provider="lifepay", event_key="tx-4:20")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Orders.FAILED)
        self.assertEqual(PaymentWebhookEvent.objects.filter(order=order).count(), 1)


# ---------------------------------------------------------------------------
# 4. Конкурентность (реальные потоки, TransactionTestCase)
# ---------------------------------------------------------------------------

class OrderConcurrencyTests(TransactionTestCase):
    """
    Два потока одновременно пытаются изменить один и тот же заказ.
    select_for_update() должен сериализовать доступ: одна транзакция ждёт
    лока, видит уже обновлённую (не устаревшую) строку после его получения.
    """

    def setUp(self):
        self.city = City.objects.create(name="Moscow")
        self.coffee_shop = make_coffee_shop(self.city)
        self.user = CustomUser.objects.create_user(login='+79990000005', password='password123')
        self.cart = ShoppingCart.objects.create(user=self.user, is_active=True)
        self.order = Orders.objects.create(
            user=self.user, city_choose=self.city, coffee_shop=self.coffee_shop,
            cart=self.cart, full_price=Decimal('300.00'),
            status_orders=Orders.IN_PROGRESS, payment_status=Orders.NEW,
        )

    def test_concurrent_payment_succeeded_and_system_cancel(self):
        """
        payment_succeeded и system-cancel запускаются "одновременно" из двух
        потоков на одном заказе. Независимо от порядка выполнения, итоговое
        состояние должно быть непротиворечивым: если PAID зафиксирован, заказ
        не должен остаться CANCELED (инвариант "PAID всегда побеждает
        поздний auto-cancel", т.к. cancel(actor_type="system") сам проверяет
        payment_status==PAID под тем же select_for_update()).
        """
        errors = []
        barrier = threading.Barrier(2)

        def do_pay():
            try:
                barrier.wait(timeout=5)
                OrderStateService.payment_succeeded(
                    self.order.id, provider="lifepay", provider_transaction_id="tx-race", event_key="tx-race:10"
                )
            except Exception as exc:  # pragma: no cover - для диагностики упавшего потока
                errors.append(exc)

        def do_cancel():
            try:
                barrier.wait(timeout=5)
                time.sleep(0.05)  # даём payment_succeeded шанс взять лок первым в большинстве прогонов
                OrderStateService.cancel(self.order.id, actor_type="system", reason="timeout race")
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        t1 = threading.Thread(target=do_pay)
        t2 = threading.Thread(target=do_cancel)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertEqual(errors, [], f"один из потоков упал: {errors}")

        self.order.refresh_from_db()
        if self.order.payment_status == Orders.PAID:
            self.assertNotEqual(
                self.order.status_orders, Orders.CANCELED,
                "PAID заказ не должен быть отменён даже при гонке с system-cancel",
            )

    def test_concurrent_double_accept_increments_version_once(self):
        self.order.status_orders = Orders.NEW
        self.order.save(update_fields=["status_orders"])

        errors = []
        barrier = threading.Barrier(2)

        def do_accept():
            try:
                barrier.wait(timeout=5)
                OrderStateService.accept(self.order.id, staff_user=None)
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=do_accept) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(errors, [])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status_orders, Orders.WAITING)
        self.assertEqual(self.order.version, 1, "два одновременных accept() должны дать ровно один реальный переход")


# ---------------------------------------------------------------------------
# 5. Авторизация (IDOR-регрессия)
# ---------------------------------------------------------------------------

class OrderAuthorizationRegressionTests(OrdersTestBase):
    """
    Сценарии 4 и 5 acceptance invariant:
    - пользователь A не может изменить заказ пользователя B, просто передав order_id;
    - анонимный запрос не может добраться до PAID/COMPLETED.
    """

    def test_customer_cannot_cancel_foreign_order(self):
        order = self.make_order(status_orders=Orders.WAITING)
        client = self.client
        self.auth(client, self.other_user)
        response = client.patch(f"/api/orders/orders/{order.id}/cancel/", content_type="application/json")
        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status_orders, Orders.WAITING)

    def test_anonymous_cannot_cancel_order(self):
        order = self.make_order(status_orders=Orders.WAITING)
        response = self.client.patch(f"/api/orders/orders/{order.id}/cancel/", content_type="application/json")
        self.assertIn(response.status_code, (401, 403))
        order.refresh_from_db()
        self.assertEqual(order.status_orders, Orders.WAITING)

    def test_staff_from_other_coffee_shop_cannot_accept_order(self):
        order = self.make_order(status_orders=Orders.NEW)
        from staff.utils import is_staff_for_order
        self.assertFalse(is_staff_for_order(self.other_shop_staff_user, order))
        self.assertTrue(is_staff_for_order(self.staff_user, order))

    def test_staff_endpoint_rejects_non_staff_user(self):
        order = self.make_order(status_orders=Orders.NEW)
        client = self.client
        self.auth(client, self.other_user)  # обычный клиент, не сотрудник ни одной кофейни
        response = client.post("/api/staff/", {"order_id": order.id}, content_type="application/json")
        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status_orders, Orders.NEW, "заказ не должен перейти в Waiting без реального staff")

    def test_admin_override_requires_reason(self):
        order = self.make_order(status_orders=Orders.WAITING)
        with self.assertRaises(OrderTransitionError):
            OrderStateService.admin_override(
                order.id, admin_user=self.staff_user, new_order_status=Orders.CANCELED, reason="", request=None
            )

    def test_admin_override_cancel_does_not_acknowledge_the_dialog(self):
        """Тот же инвариант, что и в test_cancel_does_not_acknowledge_the_cancellation_dialog:
        отмена из админки тоже не должна гасить диалог до его показа клиенту."""
        order = self.make_order(status_orders=Orders.WAITING)
        OrderStateService.admin_override(
            order.id, admin_user=self.staff_user, new_order_status=Orders.CANCELED,
            reason="test override", request=None,
        )
        order.refresh_from_db()
        self.assertEqual(order.status_orders, Orders.CANCELED)
        self.assertFalse(
            OrderDialogAck.objects.filter(order=order, dialog_key=OrderDialogAck.CANCELED).exists()
        )

    def test_client_confirmation_ownership_enforced(self):
        order = self.make_order(status_orders=Orders.WAITING)
        client = self.client
        self.auth(client, self.other_user)
        response = client.post(f"/api/orders/orders/{order.id}/client_confirmation/", content_type="application/json")
        # OrderViewSet.get_queryset() уже скоупит заказы на request.user (orders/views.py:146-149),
        # поэтому self.get_object() для чужого order.id даёт 404, а не 403 — DRF просто не
        # находит объект в queryset другого пользователя (ownership enforced раньше, чем
        # выполнился бы внутренний if order.user != request.user).
        self.assertEqual(response.status_code, 404)


class OrderListOrderingRegressionTests(OrdersTestBase):
    """
    M6 blocker: GET /api/orders/orders/ должен возвращать заказы в
    детерминированном порядке (по id), иначе мобильное приложение (которое
    берёт `list.last` как самый свежий заказ — OrderNotificationScope,
    OrderViewBLoC.lastOrder) может показать confirmation/waiting диалог не
    для того заказа, а то и вовсе не показать его для только что созданного.

    Без order_by() в OrderViewSet.get_queryset() Postgres не гарантирует
    порядок строк, и он реально плавает после UPDATE (OrderStateService
    двигает MVCC-версию строки) — этот тест воспроизводит ровно такой сценарий:
    создать несколько заказов, затем обновить один из САМЫХ РАННИХ через
    реальный state transition, и убедиться, что самый последний по времени
    создания заказ всё равно остаётся последним в ответе API.
    """

    def test_newest_order_is_last_even_after_updating_an_older_order(self):
        client = self.client
        self.auth(client, self.user)

        orders = [self.make_order(status_orders=Orders.NEW) for _ in range(4)]
        newest = orders[-1]

        # Обновляем самый первый (старый) заказ реальным переходом — именно
        # такой UPDATE на старой строке и разваливал порядок без order_by().
        OrderStateService.accept(orders[0].id, staff_user=self.staff_user)

        response = client.get("/api/orders/orders/")
        self.assertEqual(response.status_code, 200)
        returned_ids = [item["id"] for item in response.data]

        self.assertEqual(
            returned_ids, sorted(returned_ids),
            "порядок заказов должен быть детерминированным (по id)",
        )
        self.assertEqual(
            returned_ids[-1], newest.id,
            "последний элемент списка должен быть самым недавно созданным заказом",
        )


# ---------------------------------------------------------------------------
# 6. Платёжная безопасность
# ---------------------------------------------------------------------------

class PaymentSecurityTests(OrdersTestBase):
    def test_payment_change_status_endpoint_removed(self):
        """P0: полностью неаутентифицированный force-PAID endpoint должен быть удалён."""
        response = self.client.post("/api/payment/change-status/", {"order_id": 1}, content_type="application/json")
        self.assertEqual(response.status_code, 404)

    def test_lifepay_webhook_ignores_forged_body_status_uses_reverified(self):
        """
        Тело webhook'а заявляет status=10 (PAID), но реальная перепроверка
        через API LifePay возвращает PENDING — должен победить реальный
        (перепроверенный) статус, а не то, что прислал вызывающий.
        """
        order = self.make_order(status_orders=Orders.WAITING, payment_status=Orders.NEW)
        invoice = LifepayInvoice.objects.create(
            user=self.user, order=order, transaction_number="forged-tx",
            payment_url="https://example.com/pay", payment_url_web="https://example.com/pay",
        )

        with patch("acquiring.views.get_lifepay_transaction_status") as mocked:
            mocked.return_value = _status("PENDING", code=15)
            response = self.client.post(
                "/lifepay-callback/",
                {"number": "forged-tx", "status": 10},  # форджим PAID в теле
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Orders.NEW, "статус из тела webhook'а не должен применяться напрямую")

    def test_check_lifepay_status_requires_ownership(self):
        order = self.make_order(status_orders=Orders.WAITING)
        client = self.client
        self.auth(client, self.other_user)
        response = client.get(f"/api/payment/lifepay/status/{order.id}/")
        self.assertEqual(response.status_code, 404, "чужой заказ не должен быть виден по id")

    def test_staff_order_update_serializer_cannot_touch_status(self):
        from orders.serializers import StaffOrderUpdateSerializer
        self.assertNotIn('status_orders', StaffOrderUpdateSerializer.Meta.fields)
        self.assertNotIn('payment_status', StaffOrderUpdateSerializer.Meta.fields)
        self.assertNotIn('version', StaffOrderUpdateSerializer.Meta.fields)


class DefaultOrderEndpointMassAssignmentTests(OrdersTestBase):
    """
    P0: OrderViewSet — стандартный ModelViewSet — не переопределяет
    update()/partial_update() и использует OrderSerializers, где
    status_orders/payment_status не read_only. Это позволяло владельцу
    заказа через голый PUT/PATCH /api/orders/orders/<id>/ (без именованных
    действий cancel/confirm/complete/pay/client_confirmation/staff-update)
    напрямую записать себе любой статус — в обход OrderStateService.
    """

    def test_owner_cannot_patch_status_via_default_endpoint(self):
        order = self.make_order(status_orders=Orders.NEW, payment_status=Orders.PENDING)
        client = self.client
        self.auth(client, self.user)
        response = client.patch(
            f"/api/orders/orders/{order.id}/",
            {"status_orders": Orders.COMPLETED, "payment_status": Orders.PAID},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 405)
        order.refresh_from_db()
        self.assertEqual(
            (order.status_orders, order.payment_status), (Orders.NEW, Orders.PENDING),
            "клиент не должен уметь напрямую выставить себе Completed/Paid через голый PATCH",
        )

    def test_owner_cannot_put_status_via_default_endpoint(self):
        order = self.make_order(status_orders=Orders.CANCELED, payment_status=Orders.NEW)
        client = self.client
        self.auth(client, self.user)
        payload = {
            "city_choose": self.city.id,
            "coffee_shop": self.coffee_shop.id,
            "status_orders": Orders.IN_PROGRESS,
            "payment_status": Orders.PAID,
        }
        response = client.put(
            f"/api/orders/orders/{order.id}/", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 405)
        order.refresh_from_db()
        self.assertEqual(
            order.status_orders, Orders.CANCELED,
            "клиент не должен уметь воскресить отменённый заказ через голый PUT",
        )


# ---------------------------------------------------------------------------
# M7 шаг 3: подтверждение диалогов (OrderDialogAck)
# ---------------------------------------------------------------------------


class DialogAckTests(OrdersTestBase):
    """
    Правило задачи: «нажал кнопку в диалоге — он закрылся и больше никогда не
    открылся». Серверная половина этого правила — здесь.
    """

    def setUp(self):
        super().setUp()
        self.order = self.make_order()
        self.auth(self.client, self.user)

    def _ack(self, dialog, order=None, client=None):
        order = order or self.order
        client = client or self.client
        return client.post(
            f"/api/orders/orders/{order.id}/dialog-ack/",
            {"dialog": dialog},
            content_type="application/json",
        )

    def test_ack_is_persisted_and_returned(self):
        response = self._ack("thank_you")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["acknowledged_dialogs"], ["thank_you"])
        self.assertTrue(
            OrderDialogAck.objects.filter(order=self.order, dialog_key="thank_you").exists()
        )

    def test_ack_is_idempotent(self):
        """Клиент ретраит ack из офлайн-очереди — повтор обязан быть 200, а не ошибкой."""
        self.assertEqual(self._ack("thank_you").status_code, 200)
        second = self._ack("thank_you")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            OrderDialogAck.objects.filter(order=self.order, dialog_key="thank_you").count(), 1
        )

    def test_second_ack_publishes_no_event(self):
        with self.captureOnCommitCallbacks(execute=True):
            self._ack("thank_you")
        self.order.refresh_from_db()
        seq_after_first = self.order.event_seq

        with self.captureOnCommitCallbacks(execute=True):
            self._ack("thank_you")
        self.order.refresh_from_db()
        self.assertEqual(self.order.event_seq, seq_after_first)

    def test_first_ack_publishes_event_without_touching_version(self):
        """Второе устройство должно закрыть диалог, но бизнес-состояние не менялось."""
        version_before = self.order.version
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                self._ack("canceled")
        self.assertEqual(mocked.call_count, 1)
        self.order.refresh_from_db()
        self.assertEqual(self.order.version, version_before)
        self.assertEqual(self.order.event_seq, 1)

    def test_unknown_dialog_key_is_rejected(self):
        response = self._ack("drop_table")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "unknown_dialog")
        self.assertFalse(OrderDialogAck.objects.filter(order=self.order).exists())

    def test_missing_dialog_field_is_rejected(self):
        response = self.client.post(
            f"/api/orders/orders/{self.order.id}/dialog-ack/", {}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_ack_foreign_order(self):
        client = self.client_class()
        self.auth(client, self.other_user)
        response = self._ack("thank_you", client=client)
        # get_object() скоупит queryset по владельцу — чужой заказ просто не существует
        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(OrderDialogAck.objects.filter(order=self.order).exists())

    def test_anonymous_cannot_ack(self):
        client = self.client_class()
        response = self._ack("thank_you", client=client)
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(OrderDialogAck.objects.filter(order=self.order).exists())

    def test_acknowledged_dialogs_travel_inside_the_order(self):
        """
        Отдельного события на ack не нужно: снапшот читается из БД в момент
        публикации, поэтому свежий ack приезжает в ближайшем же кадре сам.
        """
        from orders.realtime import serialize_for_customer

        self._ack("thank_you")
        self._ack("feedback")
        payload = serialize_for_customer(
            Orders.objects.prefetch_related("dialog_acks").get(pk=self.order.id)
        )
        self.assertEqual(payload["acknowledged_dialogs"], ["feedback", "thank_you"])

    def test_rest_list_also_exposes_acknowledged_dialogs(self):
        """REST — аварийный fallback, он обязан отдавать то же самое."""
        self._ack("canceled")
        response = self.client.get("/api/orders/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[-1]["acknowledged_dialogs"], ["canceled"])

    def test_only_state_driven_dialogs_are_absent_from_keys(self):
        """
        Диалоги «ожидание подтверждения» и «время изменено» гасятся доменным
        состоянием, а не ack: записав им подтверждение, мы скрыли бы диалог у
        пользователя, который так и не принял решение.
        """
        self.assertEqual(
            OrderDialogAck.DIALOG_KEYS, {"thank_you", "canceled", "feedback"}
        )
        for state_driven in ("waiting_confirmation", "time_changed"):
            self.assertEqual(self._ack(state_driven).status_code, 400)


# ---------------------------------------------------------------------------
# M7 шаг 4: серверный опрос провайдера вместо клиентского
# ---------------------------------------------------------------------------


class ServerSidePaymentPollingTests(OrdersTestBase):
    """
    Опрос оплаты переехал с клиента на сервер: раньше мобильное приложение само
    дёргало /api/payment/lifepay/status/{id}/ (_checkLifePayStatus), то есть опрос
    платежа был ровно тем HTTP-запросом, от которого мы уходим. Теперь этим
    занимается Celery-цепочка, а клиент узнаёт результат обычным WS-событием.
    """

    def _in_payment(self, **overrides):
        now = timezone.now()
        defaults = dict(
            status_orders=Orders.WAITING,
            payment_status=Orders.PENDING,
            payment_started_at=now,
            payment_deadline_at=now + timedelta(seconds=60),
        )
        defaults.update(overrides)
        return self.make_order(**defaults)

    def test_paid_applies_transition_and_stops_polling(self):
        order = self._in_payment()
        with self.captureOnCommitCallbacks(execute=True):
            should_continue = OrderStateService.sync_payment_from_provider(
                order.id, provider_status_checker=lambda o: _status("PAID")
            )
        self.assertFalse(should_continue)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Orders.PAID)
        self.assertEqual(order.status_orders, Orders.IN_PROGRESS)

    def test_paid_publishes_event_so_client_learns_without_asking(self):
        """Смысл всего шага: клиент не спрашивает — ему сообщают."""
        order = self._in_payment()
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.sync_payment_from_provider(
                    order.id, provider_status_checker=lambda o: _status("PAID")
                )
        self.assertEqual(mocked.call_count, 1)

    def test_pending_keeps_polling_without_touching_state(self):
        order = self._in_payment()
        should_continue = OrderStateService.sync_payment_from_provider(
            order.id, provider_status_checker=lambda o: _status("PENDING")
        )
        self.assertTrue(should_continue)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Orders.PENDING)

    def test_missing_invoice_keeps_polling(self):
        """NOT_FOUND — инвойс ещё не создан, а не отказ: перестать опрашивать нельзя."""
        order = self._in_payment()
        self.assertTrue(
            OrderStateService.sync_payment_from_provider(
                order.id, provider_status_checker=lambda o: _status("NOT_FOUND")
            )
        )

    def test_failed_stops_polling_but_does_not_cancel_order(self):
        """Отмена — решение deadline-задачи; дублировать его в двух местах нельзя."""
        order = self._in_payment()
        with self.captureOnCommitCallbacks(execute=True):
            should_continue = OrderStateService.sync_payment_from_provider(
                order.id, provider_status_checker=lambda o: _status("FAILED")
            )
        self.assertFalse(should_continue)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Orders.FAILED)
        self.assertNotEqual(order.status_orders, Orders.CANCELED)

    def test_stops_after_deadline_without_calling_provider(self):
        order = self._in_payment(payment_deadline_at=timezone.now() - timedelta(seconds=1))
        checker = mock.Mock()
        self.assertFalse(
            OrderStateService.sync_payment_from_provider(order.id, provider_status_checker=checker)
        )
        checker.assert_not_called()

    def test_stops_for_terminal_order_without_calling_provider(self):
        order = self._in_payment(status_orders=Orders.CANCELED)
        checker = mock.Mock()
        self.assertFalse(
            OrderStateService.sync_payment_from_provider(order.id, provider_status_checker=checker)
        )
        checker.assert_not_called()

    def test_stops_when_payment_never_started(self):
        order = self._in_payment(payment_status=Orders.NEW, payment_started_at=None)
        checker = mock.Mock()
        self.assertFalse(
            OrderStateService.sync_payment_from_provider(order.id, provider_status_checker=checker)
        )
        checker.assert_not_called()

    def test_payment_started_schedules_the_poll(self):
        """Цепочка должна стартовать сама, без участия клиента."""
        order = self.make_order(status_orders=Orders.WAITING, payment_status=Orders.NEW)
        with mock.patch("orders.tasks.poll_payment_status_task.apply_async") as scheduled:
            with self.captureOnCommitCallbacks(execute=True):
                OrderStateService.payment_started(order.id, provider="lifepay")
        scheduled.assert_called_once()
        self.assertEqual(scheduled.call_args.kwargs["args"], [order.id])

    def test_poll_task_reschedules_only_while_pending(self):
        from orders.tasks import poll_payment_status_task

        order = self._in_payment()
        with mock.patch(
            "orders.services.OrderStateService.sync_payment_from_provider", return_value=True
        ):
            with mock.patch("orders.tasks.poll_payment_status_task.apply_async") as scheduled:
                poll_payment_status_task(order.id)
        scheduled.assert_called_once()

        with mock.patch(
            "orders.services.OrderStateService.sync_payment_from_provider", return_value=False
        ):
            with mock.patch("orders.tasks.poll_payment_status_task.apply_async") as scheduled:
                poll_payment_status_task(order.id)
        scheduled.assert_not_called()


# ---------------------------------------------------------------------------
# M7 (регресс из прода): админка Django как точка мутации состояния
# ---------------------------------------------------------------------------


class DjangoAdminPublishesEventsTests(OrdersTestBase):
    """
    Смена статуса через админку Django обязана публиковать событие.

    Это тот самый пропуск, из-за которого «статус изменили, а диалог не
    закрылся»: инвентаризация точек мутации в аудите покрыла HTTP-эндпоинты,
    Celery и сигналы, но не ModelAdmin. Пока клиент перечитывал заказы каждые
    5 секунд, обход сервиса был незаметен — после отказа от поллинга он означает,
    что приложение не узнает об изменении никогда.
    """

    class _Form:
        """Минимальная замена ModelForm: админке от неё нужны только эти два поля."""

        def __init__(self, changed_data, initial):
            self.changed_data = changed_data
            self.initial = initial

    def setUp(self):
        super().setUp()
        from django.contrib.admin.sites import AdminSite

        from orders.admin import OrdersAdmin

        from django.test import RequestFactory

        self.admin = OrdersAdmin(Orders, AdminSite())
        # Настоящий request: audit-логгер читает META (IP, user-agent).
        self.request = RequestFactory().post('/admin/orders/orders/1/change/')
        self.request.user = self.staff_user

    def _save_via_admin(self, order, **new_values):
        initial = {
            'status_orders': order.status_orders,
            'payment_status': order.payment_status,
        }
        for field, value in new_values.items():
            setattr(order, field, value)
        form = self._Form(list(new_values), initial)
        self.admin.save_model(self.request, order, form, change=True)

    def test_status_change_publishes_event(self):
        order = self.make_order(status_orders=Orders.NEW)
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                self._save_via_admin(order, status_orders=Orders.WAITING)

        self.assertEqual(mocked.call_count, 1)
        order.refresh_from_db()
        self.assertEqual(order.status_orders, Orders.WAITING)
        self.assertEqual(order.event_seq, 1)

    def test_payment_status_change_publishes_event(self):
        order = self.make_order(status_orders=Orders.WAITING)
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                self._save_via_admin(order, payment_status=Orders.PENDING)

        self.assertEqual(mocked.call_count, 1)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Orders.PENDING)

    def test_both_fields_change_publishes_single_event(self):
        """Ровно тот сценарий из отчёта: «Ожидание» + «ожидание оплаты» разом."""
        order = self.make_order(status_orders=Orders.NEW, payment_status=Orders.NEW)
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                self._save_via_admin(
                    order,
                    status_orders=Orders.WAITING,
                    payment_status=Orders.PENDING,
                )

        self.assertEqual(mocked.call_count, 1)
        order.refresh_from_db()
        self.assertEqual(order.status_orders, Orders.WAITING)
        self.assertEqual(order.payment_status, Orders.PENDING)

    def test_editing_only_presentation_fields_publishes_nothing(self):
        """Правка комментария — не переход состояния, событие тут ни к чему."""
        order = self.make_order(status_orders=Orders.WAITING)
        with mock.patch("orders.services.publish_order_status_changed") as mocked:
            with self.captureOnCommitCallbacks(execute=True):
                order.staff_comments = 'заметка бариста'
                form = self._Form(['staff_comments'], {})
                self.admin.save_model(self.request, order, form, change=True)

        self.assertEqual(mocked.call_count, 0)

    def test_status_change_is_audited(self):
        from admin_api.models import AdminActivityLog

        order = self.make_order(status_orders=Orders.NEW)
        with self.captureOnCommitCallbacks(execute=True):
            self._save_via_admin(order, status_orders=Orders.WAITING)

        self.assertTrue(
            AdminActivityLog.objects.filter(entity_name='Orders', entity_id=order.id).exists()
        )
