"""
M7 (регресс с живого стенда): отправка отзыва падала целиком.

Симптом: пользователь жмёт «Оценить», кнопка уходит в прогресс и остаётся с
ошибкой. Причина — на сервере: в теле запроса выполнялась синхронная отправка
в Telegram (requests.get к api.telegram.org) и письмо, без обработки ошибок.
Недоступность любого из них превращала запрос в 500, и отзыв не сохранялся.

Мобильное приложение это раньше скрывало: диалог закрывался в finally
независимо от результата — поэтому баг годами выглядел как «диалог оценки
иногда возвращается» (is_appreciated не выставлялся), а не как отказ.
"""
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

    def test_review_is_accepted_when_telegram_is_unreachable(self):
        """Ровно тот отказ, который видел пользователь: Telegram недоступен."""
        with mock.patch(
            'reviews.views.send_review_to_user', side_effect=OSError('telegram unreachable')
        ):
            response = self._post()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(ReviewsCoffeeShop.objects.filter(orders=self.order).exists())

    def test_review_is_accepted_when_email_notification_fails(self):
        with mock.patch(
            'reviews.views.check_negative_feedback', side_effect=OSError('smtp down')
        ):
            response = self._post()

        self.assertEqual(response.status_code, 201)

    def test_order_is_marked_appreciated_even_if_notifications_fail(self):
        """
        Главное следствие прежнего порядка действий: отзыв мог сохраниться, а
        is_appreciated — нет, и диалог оценки возвращался снова и снова.
        """
        with mock.patch('reviews.views.send_review_to_user', side_effect=OSError('boom')):
            with self.captureOnCommitCallbacks(execute=True):
                self._post()

        self.order.refresh_from_db()
        self.assertTrue(self.order.is_appreciated)

    def test_successful_review_publishes_event(self):
        """Оценка гасит диалог, значит клиент обязан узнать об этом событием."""
        with mock.patch('reviews.views.send_review_to_user'):
            with mock.patch('orders.services.publish_order_status_changed') as mocked:
                with self.captureOnCommitCallbacks(execute=True):
                    self._post()

        self.assertEqual(mocked.call_count, 1)

    def test_invalid_evaluation_is_still_rejected(self):
        """Обработка ошибок уведомлений не должна проглатывать валидацию."""
        with mock.patch('reviews.views.send_review_to_user'):
            response = self._post(evaluation=9)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ReviewsCoffeeShop.objects.filter(orders=self.order).exists())
