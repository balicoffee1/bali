from decimal import Decimal
from unittest import mock

from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from cart.models import ShoppingCart
from coffee_shop.models import City
from orders.models import Orders
from orders.tests import make_coffee_shop
from reviews.models import ReviewsCoffeeShop
from users.models import CustomUser


class ReviewSubmissionTests(TestCase):
    def setUp(self):
        self.city = City.objects.create(name="Moscow")
        self.coffee_shop = make_coffee_shop(self.city)
        self.coffee_shop.telegram_id = '123456'
        self.coffee_shop.save(update_fields=['telegram_id'])
        self.user = CustomUser.objects.create_user(login='+79990000001', password='pw')
        self.cart = ShoppingCart.objects.create(user=self.user, is_active=True)
        self.order = Orders.objects.create(
            user=self.user,
            city_choose=self.city,
            coffee_shop=self.coffee_shop,
            cart=self.cart,
            full_price=Decimal('300.00'),
            status_orders=Orders.COMPLETED,
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'

    def _payload(self, **overrides):
        payload = {
            'coffee_shop': self.coffee_shop.id,
            'orders': self.order.id,
            'evaluation': 5,
            'comments': 'вкусно',
        }
        payload.update(overrides)
        return payload

    def _post(self, **overrides):
        return self.client.post(
            '/api/review/', self._payload(**overrides), content_type='application/json'
        )

    def test_review_is_accepted_when_notification_cannot_be_enqueued(self):
        """Сбой фоновой инфраструктуры не меняет успешный результат отзыва."""
        with mock.patch(
            'reviews.views.send_review_to_telegram.delay',
            side_effect=OSError('broker unreachable'),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = self._post()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(ReviewsCoffeeShop.objects.filter(orders=self.order).exists())

    def test_negative_review_is_queued_instead_of_sending_in_request(self):
        with mock.patch('reviews.views.send_review_to_telegram.delay') as telegram_delay:
            with mock.patch('reviews.views.send_review_for_email.delay') as email_delay:
                with self.captureOnCommitCallbacks(execute=True):
                    response = self._post(evaluation=2)

        self.assertEqual(response.status_code, 201)
        telegram_delay.assert_called_once()
        email_delay.assert_called_once()

    def test_order_is_marked_appreciated(self):
        with mock.patch('reviews.views.send_review_to_telegram.delay'):
            with self.captureOnCommitCallbacks(execute=True):
                self._post()

        self.order.refresh_from_db()
        self.assertTrue(self.order.is_appreciated)

    def test_successful_review_publishes_event(self):
        """Оценка гасит диалог, значит клиент обязан узнать об этом событием."""
        with mock.patch('reviews.views.send_review_to_telegram.delay'):
            with mock.patch('orders.services.publish_order_status_changed') as mocked:
                with self.captureOnCommitCallbacks(execute=True):
                    self._post()

        self.assertEqual(mocked.call_count, 1)

    def test_invalid_evaluation_is_still_rejected(self):
        response = self._post(evaluation=9)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ReviewsCoffeeShop.objects.filter(orders=self.order).exists())

    def test_duplicate_submission_is_idempotent(self):
        with mock.patch('reviews.views.send_review_to_telegram.delay') as telegram_delay:
            with self.captureOnCommitCallbacks(execute=True):
                first = self._post()
            with self.captureOnCommitCallbacks(execute=True):
                second = self._post()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(ReviewsCoffeeShop.objects.filter(orders=self.order).count(), 1)
        telegram_delay.assert_called_once()

    def test_cannot_review_another_users_order(self):
        other_user = CustomUser.objects.create_user(login='+79990000002', password='pw')
        self.order.user = other_user
        self.order.save(update_fields=['user'])

        response = self._post()

        self.assertEqual(response.status_code, 404)
        self.assertFalse(ReviewsCoffeeShop.objects.filter(orders=self.order).exists())

    def test_coffee_shop_must_match_order(self):
        other_shop = make_coffee_shop(City.objects.create(name='Kazan'))

        response = self._post(coffee_shop=other_shop.id)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ReviewsCoffeeShop.objects.filter(orders=self.order).exists())

    def test_only_completed_order_can_be_reviewed(self):
        self.order.status_orders = Orders.IN_PROGRESS
        self.order.save(update_fields=['status_orders'])

        response = self._post()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ReviewsCoffeeShop.objects.filter(orders=self.order).exists())
