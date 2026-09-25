from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch, MagicMock

from admin_api.models import AdminActivityLog
from coffee_shop.models import City, CoffeeShop, CrmSystem, Acquiring
from users.models import CustomUser


class AdminUserSerializerPrivilegeTests(TestCase):
    """
    AdminUserSerializer отдавал role, is_staff и is_superuser на запись, а
    ModelViewSet принимает их и на POST, и на PATCH. То есть любой admin мог
    создать себе суперпользователя или поднять роль обычным запросом к
    /api/admin/users/, минуя set_role, закрытый IsSuperAdmin.
    """

    def setUp(self):
        self.owner = CustomUser.objects.create_user(
            login='+79990000001', password='pw', role='owner', first_name='Owner'
        )
        self.admin = CustomUser.objects.create_user(
            login='+79990000002', password='pw', role='admin', first_name='Admin'
        )

    def auth_as(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'

    def payload(self, **overrides):
        data = {
            'login': '+79995550011',
            'first_name': 'Динара',
            'last_name': 'Сафина',
            'phone_number': '+79995550011',
            'role': 'employee',
        }
        data.update(overrides)
        return data

    def create_user(self, **overrides):
        return self.client.post(
            '/api/admin/users/',
            data=self.payload(**overrides),
            content_type='application/json',
        )

    # ---------------------------------------------------------------- create

    def test_admin_cannot_create_superuser(self):
        self.auth_as(self.admin)
        response = self.create_user(is_superuser=True, is_staff=True)

        self.assertEqual(response.status_code, 201, response.data)
        created = CustomUser.objects.get(login='+79995550011')
        self.assertFalse(created.is_superuser)
        self.assertFalse(created.is_staff)

    def test_admin_cannot_create_privileged_role(self):
        self.auth_as(self.admin)
        for role in ('owner', 'admin', 'moderator', 'support'):
            with self.subTest(role=role):
                response = self.create_user(role=role, login=f'+7999555{role[:4]}')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('role', response.data)

    def test_admin_can_create_employee(self):
        self.auth_as(self.admin)
        response = self.create_user()

        self.assertEqual(response.status_code, 201, response.data)
        created = CustomUser.objects.get(login='+79995550011')
        self.assertEqual(created.role, 'employee')
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)

    def test_owner_can_create_admin_and_flag_follows_role(self):
        self.auth_as(self.owner)
        response = self.create_user(role='admin')

        self.assertEqual(response.status_code, 201, response.data)
        created = CustomUser.objects.get(login='+79995550011')
        self.assertEqual(created.role, 'admin')
        # is_staff выводится из роли, а не берётся из запроса.
        self.assertTrue(created.is_staff)
        self.assertFalse(created.is_superuser)

    def test_creation_is_written_to_audit_log(self):
        self.auth_as(self.admin)
        self.create_user()

        log = AdminActivityLog.objects.filter(
            action='CREATE', entity_name='CustomUser'
        ).first()
        self.assertIsNotNone(log)
        self.assertIn('+79995550011', log.summary)

    # ---------------------------------------------------------------- update

    def test_admin_cannot_escalate_existing_user_via_patch(self):
        target = CustomUser.objects.create_user(
            login='+79995550022', password='pw', role='user', first_name='Client'
        )
        self.auth_as(self.admin)

        response = self.client.patch(
            f'/api/admin/users/{target.id}/',
            data={'role': 'admin', 'is_superuser': True},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400, response.data)
        target.refresh_from_db()
        self.assertEqual(target.role, 'user')
        self.assertFalse(target.is_superuser)
        self.assertFalse(target.is_staff)

    def test_admin_cannot_grant_itself_superuser_via_patch(self):
        self.auth_as(self.admin)

        response = self.client.patch(
            f'/api/admin/users/{self.admin.id}/',
            data={'is_superuser': True, 'is_staff': True},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_superuser)
        # admin — привилегированная роль, поэтому is_staff остаётся True,
        # но именно потому что так говорит роль, а не запрос.
        self.assertTrue(self.admin.is_staff)

    def test_owner_can_still_change_role_via_patch(self):
        target = CustomUser.objects.create_user(
            login='+79995550033', password='pw', role='user', first_name='Client'
        )
        self.auth_as(self.owner)

        response = self.client.patch(
            f'/api/admin/users/{target.id}/',
            data={'role': 'moderator'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        target.refresh_from_db()
        self.assertEqual(target.role, 'moderator')
        self.assertFalse(target.is_staff)


class AdminCoffeeShopTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            login='+79990000003', password='pw', role='admin', first_name='Admin'
        )
        self.city = City.objects.create(name='Казань')
        self.crm = CrmSystem.objects.create(name='QuickRestoApi')
        self.acquiring = Acquiring.objects.create(
            for_coffeeshop='Test', name='RussianStandart', login='l', password='p'
        )

    def auth_as(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'

    def test_create_coffee_shop_minimal_fields(self):
        self.auth_as(self.admin)
        response = self.client.post(
            '/api/admin/coffee-shops/',
            data={'city': self.city.id, 'street': 'Баумана'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        shop = CoffeeShop.objects.get(id=response.data['id'])
        self.assertEqual(shop.street, 'Баумана')
        self.assertEqual(shop.city, self.city)
        # Network defaults auto-assigned
        self.assertEqual(shop.crm_system, self.crm)
        self.assertEqual(shop.acquiring, self.acquiring)

        # Audit log created
        log = AdminActivityLog.objects.filter(action='CREATE', entity_name='CoffeeShop').first()
        self.assertIsNotNone(log)

    def test_create_coffee_shop_international_phone(self):
        self.auth_as(self.admin)
        response = self.client.post(
            '/api/admin/coffee-shops/',
            data={
                'city': self.city.id,
                'street': 'Jl. Pantai Batu Bolong',
                'building_number': '14A',
                'phone_number': '+62 812 3456 7890',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        shop = CoffeeShop.objects.get(id=response.data['id'])
        self.assertEqual(shop.phone_number, '+62 812 3456 7890')

    def test_create_coffee_shop_blank_optional_fields(self):
        self.auth_as(self.admin)
        response = self.client.post(
            '/api/admin/coffee-shops/',
            data={
                'city': self.city.id,
                'street': 'Пушкина',
                'building_number': '',
                'crm_email': '',
                'crm_layer_name': '',
                'telegram_username': '',
                'phone_number': '',
                'inn': '',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201, response.data)

    def test_create_coffee_shop_missing_street_fails(self):
        self.auth_as(self.admin)
        response = self.client.post(
            '/api/admin/coffee-shops/',
            data={'city': self.city.id},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('street', response.data)


class LifePayIntegrationTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            login='+79990000004', password='pw', role='admin', first_name='Admin'
        )
        self.city = City.objects.create(name='Омск')

    def auth_as(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'

    def test_normalize_lifepay_login(self):
        from acquiring.providers import normalize_lifepay_login

        cases = [
            ('+79872716165', '79872716165'),
            ('+7 (987) 271-61-65', '79872716165'),
            ('89872716165', '79872716165'),
            ('9872716165', '79872716165'),
            ('79872716165', '79872716165'),
            ('admin@company.ru', 'admin@company.ru'),
            ('', ''),
            (None, ''),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_lifepay_login(raw), expected)

    def test_coffee_shop_save_normalizes_lifepay_login(self):
        shop = CoffeeShop.objects.create(
            city=self.city,
            street='10 лет октября',
            lifepay_login='+79872716165',
            lifepay_api_key='test_key',
        )
        shop.refresh_from_db()
        self.assertEqual(shop.lifepay_login, '79872716165')

    def test_admin_api_creates_coffee_shop_with_normalized_lifepay_login(self):
        self.auth_as(self.admin)
        response = self.client.post(
            '/api/admin/coffee-shops/',
            data={
                'city': self.city.id,
                'street': 'Ленина',
                'lifepay_login': '+7 (987) 271-61-65',
                'lifepay_api_key': 'test_api_key',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        shop = CoffeeShop.objects.get(id=response.data['id'])
        self.assertEqual(shop.lifepay_login, '79872716165')

    def test_admin_api_test_lifepay_detects_nonzero_code_as_error(self):
        from unittest.mock import patch, MagicMock
        self.auth_as(self.admin)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'code': 6010,
            'message': 'Несоответствие apikey и login',
            'data': {}
        }

        with patch('requests.get', return_value=mock_resp):
            response = self.client.post(
                '/api/admin/coffee-shops/test-lifepay/',
                data={
                    'lifepay_api_key': 'test_key',
                    'lifepay_login': '+79872716165',
                },
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.data['valid'])
            self.assertIn('Несоответствие apikey и login', response.data['error'])

    def test_admin_api_test_lifepay_success_on_code_zero(self):
        from unittest.mock import patch, MagicMock
        self.auth_as(self.admin)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'code': 0,
            'message': '',
            'data': {}
        }

        with patch('requests.get', return_value=mock_resp) as mock_get:
            response = self.client.post(
                '/api/admin/coffee-shops/test-lifepay/',
                data={
                    'lifepay_api_key': 'valid_key',
                    'lifepay_login': '+79872716165',
                },
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data['valid'])
            # Verify login was normalized before being sent to LifePay
            params = mock_get.call_args.kwargs['params']
            self.assertEqual(params['login'], '79872716165')


class TelegramIntegrationTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            login='+79990000005', password='pw', role='admin', first_name='Admin'
        )
        self.city = City.objects.create(name='Казань')
        self.shop = CoffeeShop.objects.create(
            city=self.city,
            street='Баумана',
            building_number='1',
        )

    def auth_as(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'

    def test_telegram_bind_link_generates_token(self):
        self.auth_as(self.admin)
        response = self.client.get(f'/api/admin/coffee-shops/{self.shop.id}/telegram-bind-link/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('link', response.data)
        self.assertIn('token', response.data)
        self.assertTrue(response.data['token'].startswith('bind_'))
        self.assertIn(response.data['token'], response.data['link'])

    def test_telegram_bind_status(self):
        self.auth_as(self.admin)
        self.shop.telegram_id = '123456789'
        self.shop.telegram_username = '@test_shop'
        self.shop.save()

        response = self.client.get(f'/api/admin/coffee-shops/{self.shop.id}/telegram-bind-status/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_connected'])
        self.assertEqual(response.data['telegram_id'], '123456789')
        self.assertEqual(response.data['telegram_username'], '@test_shop')

    def test_test_telegram_action(self):
        self.auth_as(self.admin)
        self.shop.telegram_id = '123456789'
        self.shop.save()

        with patch('reviews.telegram_bot.send_review_to_user', return_value={'ok': True}) as mock_send:
            response = self.client.post(f'/api/admin/coffee-shops/{self.shop.id}/test-telegram/')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data['success'])
            mock_send.assert_called_once()

    def test_unlink_telegram_action(self):
        self.auth_as(self.admin)
        self.shop.telegram_id = '123456789'
        self.shop.telegram_username = '@test_shop'
        self.shop.save()

        response = self.client.post(f'/api/admin/coffee-shops/{self.shop.id}/unlink-telegram/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])

        self.shop.refresh_from_db()
        self.assertIsNone(self.shop.telegram_id)
        self.assertEqual(self.shop.telegram_username, '')

    def test_run_telegram_bot_process_bind_command(self):
        from coffee_shop.management.commands.run_telegram_bot import Command
        from django.core.cache import cache

        cmd = Command()
        token = "bind_test123"
        cache.set(f"tg_bind_{token}", self.shop.id, timeout=300)

        message = {
            "chat": {"id": 999888777},
            "from": {"username": "barista_boss", "first_name": "Иван"},
            "text": f"/start {token}"
        }

        with patch('reviews.telegram_bot.send_review_to_user', return_value={'ok': True}) as mock_send:
            cmd.process_message(message)
            self.shop.refresh_from_db()
            self.assertEqual(self.shop.telegram_id, "999888777")
            self.assertEqual(self.shop.telegram_username, "@barista_boss")
            mock_send.assert_called_once()
            self.assertIn("успешно подключена", mock_send.call_args[0][1])

            # Check cache status
            status_data = cache.get(f"tg_bind_status_{token}")
            self.assertIsNotNone(status_data)
            self.assertEqual(status_data["status"], "linked")
            self.assertEqual(status_data["shop_id"], self.shop.id)


class TelegramBotInteractiveFeaturesTests(TestCase):
    def setUp(self):
        from decimal import Decimal
        from django.utils import timezone
        from cart.models import ShoppingCart, CartItem
        from coffee_shop.models import City, CoffeeShop
        from menu_coffee_product.models import Category, Product
        from orders.models import Orders
        from reviews.models import ReviewsCoffeeShop
        from staff.models import Staff, Shift
        from users.models import CustomUser

        self.city = City.objects.create(name='Казань')
        self.shop = CoffeeShop.objects.create(
            city=self.city,
            street='ул. Кремлевская',
            building_number='10',
            telegram_id='555666777',
            telegram_username='@test_manager',
        )
        self.user = CustomUser.objects.create_user(
            login='+79998881122', password='pw', first_name='Алексей'
        )
        self.category = Category.objects.create(
            coffee_shop=self.shop, name='Кофе'
        )
        self.product = Product.objects.create(
            coffee_shop=self.shop,
            category=self.category,
            product='Капучино',
            price=Decimal('250.00'),
            product_type='coffee',
        )
        self.cart = ShoppingCart.objects.create(user=self.user)
        self.cart_item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            amount=2,
            size='M',
        )
        self.order = Orders.objects.create(
            user=self.user,
            city_choose=self.city,
            coffee_shop=self.shop,
            cart=self.cart,
            full_price=Decimal('500.00'),
            status_orders=Orders.COMPLETED,
            payment_status=Orders.PAID,
            created_at=timezone.now(),
            client_comments='Без сахара, пожалуйста',
        )
        self.review = ReviewsCoffeeShop.objects.create(
            coffee_shop=self.shop,
            user=self.user,
            orders=self.order,
            evaluation=5,
            very_tasty=True,
            comments='Отличный капучино!',
        )

    def test_unbound_user_message(self):
        from coffee_shop.management.commands.run_telegram_bot import Command
        cmd = Command()
        message = {
            "chat": {"id": 111222333},
            "from": {"first_name": "Незнакомец"},
            "text": "💬 История отзывов"
        }
        with patch('reviews.telegram_bot.send_review_to_user', return_value={'ok': True}) as mock_send:
            cmd.process_message(message)
            mock_send.assert_called_once()
            self.assertIn("Кофейня не привязана", mock_send.call_args[0][1])

    def test_start_bound_user(self):
        from coffee_shop.management.commands.run_telegram_bot import Command
        cmd = Command()
        message = {
            "chat": {"id": 555666777},
            "from": {"first_name": "Менеджер"},
            "text": "/start"
        }
        with patch('reviews.telegram_bot.send_review_to_user', return_value={'ok': True}) as mock_send:
            cmd.process_message(message)
            mock_send.assert_called_once()
            self.assertIn("Вы подключены к кофейням", mock_send.call_args[0][1])
            self.assertIsNotNone(mock_send.call_args.kwargs.get('reply_markup'))

    def test_reviews_history(self):
        from coffee_shop.management.commands.run_telegram_bot import Command
        cmd = Command()
        message = {
            "chat": {"id": 555666777},
            "from": {"first_name": "Менеджер"},
            "text": "💬 История отзывов"
        }
        with patch('reviews.telegram_bot.send_review_to_user', return_value={'ok': True}) as mock_send:
            cmd.process_message(message)
            mock_send.assert_called_once()
            text = mock_send.call_args[0][1]
            self.assertIn("История отзывов", text)
            self.assertIn("⭐⭐⭐⭐⭐", text)
            self.assertIn("Алексей", text)
            self.assertIn("Отличный капучино!", text)
            self.assertIn("#вкусно", text)

    def test_orders_history(self):
        from coffee_shop.management.commands.run_telegram_bot import Command
        cmd = Command()
        message = {
            "chat": {"id": 555666777},
            "from": {"first_name": "Менеджер"},
            "text": "📦 История заказов"
        }
        with patch('reviews.telegram_bot.send_review_to_user', return_value={'ok': True}) as mock_send:
            cmd.process_message(message)
            mock_send.assert_called_once()
            text = mock_send.call_args[0][1]
            self.assertIn("История заказов", text)
            self.assertIn(f"Заказ #{self.order.id}", text)
            self.assertIn("🟢 Выполнен", text)
            self.assertIn("💳 Оплачено", text)
            self.assertIn("500.00 ₽", text)
            self.assertIn("Капучино (M) x2", text)
            self.assertIn("Без сахара, пожалуйста", text)

    def test_today_summary(self):
        from coffee_shop.management.commands.run_telegram_bot import Command
        cmd = Command()
        message = {
            "chat": {"id": 555666777},
            "from": {"first_name": "Менеджер"},
            "text": "📊 Сводка за сегодня"
        }
        with patch('reviews.telegram_bot.send_review_to_user', return_value={'ok': True}) as mock_send:
            cmd.process_message(message)
            mock_send.assert_called_once()
            text = mock_send.call_args[0][1]
            self.assertIn("Сводка за сегодня", text)
            self.assertIn("500.00 ₽", text)
            self.assertIn("Закрыто чеков:</b> 1", text)
            self.assertIn("Отзывов за сегодня:</b> 1", text)
            self.assertIn("5.0 / 5.0", text)

    def test_current_shift(self):
        from staff.models import Staff, Shift
        from django.utils import timezone
        from coffee_shop.management.commands.run_telegram_bot import Command

        staff = Staff.objects.create(users=self.user, place_of_work=self.shop)
        Shift.objects.create(
            staff=staff,
            start_time=timezone.now(),
            status_shift="Open",
            number_orders_closed=3,
            amount_closed_orders=1500.00,
        )

        cmd = Command()
        message = {
            "chat": {"id": 555666777},
            "from": {"first_name": "Менеджер"},
            "text": "⏱ Текущая смена"
        }
        with patch('reviews.telegram_bot.send_review_to_user', return_value={'ok': True}) as mock_send:
            cmd.process_message(message)
            mock_send.assert_called_once()
            text = mock_send.call_args[0][1]
            self.assertIn("Открытая смена", text)
            self.assertIn("Алексей", text)

    def test_my_shops(self):
        from coffee_shop.management.commands.run_telegram_bot import Command
        cmd = Command()
        message = {
            "chat": {"id": 555666777},
            "from": {"first_name": "Менеджер"},
            "text": "📍 Мои кофейни"
        }
        with patch('reviews.telegram_bot.send_review_to_user', return_value={'ok': True}) as mock_send:
            cmd.process_message(message)
            mock_send.assert_called_once()
            text = mock_send.call_args[0][1]
            self.assertIn("Ваши подключенные кофейни", text)
            self.assertIn("Кремлевская", text)
            self.assertIn("555666777", text)

    def test_callback_query_pagination(self):
        from coffee_shop.management.commands.run_telegram_bot import Command
        cmd = Command()
        callback = {
            "id": "cb_12345",
            "from": {"id": 555666777},
            "data": "rev_more_0",
        }
        with patch('reviews.telegram_bot.answer_callback_query', return_value={'ok': True}) as mock_ack, \
             patch('reviews.telegram_bot.send_review_to_user', return_value={'ok': True}) as mock_send:
            cmd.process_callback_query(callback)
            mock_ack.assert_called_once_with("cb_12345")
            mock_send.assert_called_once()
            self.assertIn("История отзывов", mock_send.call_args[0][1])


