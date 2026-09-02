"""
M1: тесты OrderStateService / state machine / payment deadline-grace /
конкурентности / авторизации / платёжной безопасности.

ВАЖНО (см. финальный отчёт M0/M1, раздел G): эти тесты НЕ были запущены в
данной сессии — здесь нет рабочего окружения с установленным Django (ни в
облачной песочнице, ни в shell на компьютере пользователя нет сетевого
доступа к PyPI, чтобы поставить зависимости из requirements.txt, и нет
Docker CLI, чтобы поднять штатное docker-compose окружение проекта). Файл
проверен только на синтаксическую корректность (`python3 -m py_compile`) и
логически вычитан вручную. Точные команды для реального запуска в
Docker-окружении пользователя — в финальном отчёте.
"""
import threading
import time
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from acquiring.providers import ProviderPaymentStatus
from acquiring.models import LifepayInvoice
from cart.models import ShoppingCart
from coffee_shop.models import Acquiring, City, CoffeeShop, CrmSystem
from orders.models import Orders, PaymentReconciliation, PaymentWebhookEvent
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
