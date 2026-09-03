from decimal import Decimal
from django.test import TestCase
from users.models import CustomUser
from coffee_shop.models import City, CoffeeShop, CrmSystem, Acquiring
from menu_coffee_product.models import Product, Addon, AdditiveFlavors, Category
from cart.models import ShoppingCart, CartItem

class CartItemPriceTestCase(TestCase):
    def setUp(self):
        # Create user
        self.user = CustomUser.objects.create_user(login='+79998887766', password='password123')
        
        # Create relations for CoffeeShop
        self.city = City.objects.create(name="Moscow")
        self.crm = CrmSystem.objects.create(name="QuickRestoApi")
        self.acquiring = Acquiring.objects.create(for_coffeeshop="Test", name="RussianStandart", login="login", password="password")
        
        # Create CoffeeShop
        self.coffeeshop = CoffeeShop.objects.create(
            city=self.city,
            street="Arbat",
            building_number="1",
            email="test@test.com",
            telegram_username="@test",
            crm_system=self.crm,
            acquiring=self.acquiring
        )
        
        # Create Category
        self.category = Category.objects.create(coffee_shop=self.coffeeshop, name="Coffee")
        
        # Create Product
        self.product = Product.objects.create(
            coffee_shop=self.coffeeshop,
            category=self.category,
            product="Lathe",
            price_s=Decimal('100.00'),
            price_m=Decimal('150.00'),
            price_l=Decimal('200.00'),
            product_type="coffee"
        )
        
        # Create Addon and Flavors
        self.addon_caramel = Addon.objects.create(
            coffee_shop=self.coffeeshop,
            name="Caramel",
            price=Decimal('20.00')
        )
        self.flavor_bubble = AdditiveFlavors.objects.create(
            coffee_shop=self.coffeeshop,
            name="bubble"
        )
        self.addon_caramel.flavors.add(self.flavor_bubble)
        
        # Create Cart and CartItem
        self.cart = ShoppingCart.objects.create(user=self.user, is_active=True)
        self.cart_item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            amount=2,
            size=CartItem.SizeChoices.S
        )

    def test_item_total_price_base(self):
        # Base product price for S size is 100.00. amount=2.
        # Total should be (100.00 + 0 + 0) * 2 = 200.00
        self.assertEqual(self.cart_item.item_total_price, Decimal('200.00'))

    def test_item_total_price_with_addon(self):
        # Add caramel addon (price 20.00)
        self.cart_item.addons.add(self.addon_caramel)
        # Total should be (100.00 + 20.00) * 2 = 240.00
        self.assertEqual(self.cart_item.item_total_price, Decimal('240.00'))

    def test_item_total_price_with_addon_and_flavor(self):
        # Add caramel addon (price 20.00) and bubble flavor (adds price of addon: 20.00)
        self.cart_item.addons.add(self.addon_caramel)
        self.cart_item.flavors.add(self.flavor_bubble)
        # Total should be (100.00 + 20.00 + 20.00) * 2 = 280.00
        self.assertEqual(self.cart_item.item_total_price, Decimal('280.00'))


class CartItemSplitViewTestCase(TestCase):
    def setUp(self):
        # Create user
        self.user = CustomUser.objects.create_user(login='+79998887766', password='password123')
        
        # Authenticate client using JWT token
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'
        
        # Create relations for CoffeeShop
        self.city = City.objects.create(name="Moscow")
        self.crm = CrmSystem.objects.create(name="QuickRestoApi")
        self.acquiring = Acquiring.objects.create(for_coffeeshop="Test", name="RussianStandart", login="login", password="password")
        
        # Create CoffeeShop
        self.coffeeshop = CoffeeShop.objects.create(
            city=self.city,
            street="Arbat",
            building_number="1",
            email="test@test.com",
            telegram_username="@test",
            crm_system=self.crm,
            acquiring=self.acquiring
        )
        
        # Create Category
        self.category = Category.objects.create(coffee_shop=self.coffeeshop, name="Coffee")
        
        # Create Product
        self.product = Product.objects.create(
            coffee_shop=self.coffeeshop,
            category=self.category,
            product="Lathe",
            price_s=Decimal('100.00'),
            price_m=Decimal('150.00'),
            price_l=Decimal('200.00'),
            product_type="coffee",
            availability=True
        )
        
        # Create Addon and Flavors
        self.addon_caramel = Addon.objects.create(
            coffee_shop=self.coffeeshop,
            name="Caramel",
            price=Decimal('20.00')
        )
        self.flavor_bubble = AdditiveFlavors.objects.create(
            coffee_shop=self.coffeeshop,
            name="bubble"
        )
        self.addon_caramel.flavors.add(self.flavor_bubble)

        from django.urls import reverse
        self.url = reverse('add_to_cart', kwargs={'city_name': 'Moscow', 'street_name': 'Arbat'})

    def test_add_same_product_same_config_merges(self):
        # Add once
        data1 = {
            "product_name": "Lathe",
            "quantity": 1,
            "size": "S",
            "temperature_type": "Hot",
            "addons": [self.addon_caramel.id],
            "flavors": [self.flavor_bubble.id]
        }
        response1 = self.client.post(self.url, data1, content_type='application/json')
        self.assertEqual(response1.status_code, 200)

        # Add second time with identical config
        response2 = self.client.post(self.url, data1, content_type='application/json')
        self.assertEqual(response2.status_code, 200)

        # Verify there is only 1 item in the cart, and its amount is 2
        cart = ShoppingCart.objects.get(user=self.user, is_active=True)
        self.assertEqual(cart.items.count(), 1)
        self.assertEqual(cart.items.first().amount, 2)

    def test_add_same_product_different_config_splits(self):
        # Add with caramel addon and bubble flavor
        data1 = {
            "product_name": "Lathe",
            "quantity": 1,
            "size": "S",
            "temperature_type": "Hot",
            "addons": [self.addon_caramel.id],
            "flavors": [self.flavor_bubble.id]
        }
        response1 = self.client.post(self.url, data1, content_type='application/json')
        self.assertEqual(response1.status_code, 200)

        # Add same product but with no addons/flavors
        data2 = {
            "product_name": "Lathe",
            "quantity": 1,
            "size": "S",
            "temperature_type": "Hot",
            "addons": [],
            "flavors": []
        }
        response2 = self.client.post(self.url, data2, content_type='application/json')
        self.assertEqual(response2.status_code, 200)

        # Verify there are 2 separate items in the cart
        cart = ShoppingCart.objects.get(user=self.user, is_active=True)
        self.assertEqual(cart.items.count(), 2)

    def test_remove_product_fallback_deletes_only_one(self):
        # Add product once
        data1 = {
            "product_name": "Lathe",
            "quantity": 1,
            "size": "S",
            "temperature_type": "Hot",
            "addons": [self.addon_caramel.id],
            "flavors": [self.flavor_bubble.id]
        }
        self.client.post(self.url, data1, content_type='application/json')

        # Add second time with different config
        data2 = {
            "product_name": "Lathe",
            "quantity": 1,
            "size": "S",
            "temperature_type": "Hot",
            "addons": [],
            "flavors": []
        }
        self.client.post(self.url, data2, content_type='application/json')

        # We have 2 items in cart
        cart = ShoppingCart.objects.get(user=self.user, is_active=True)
        self.assertEqual(cart.items.count(), 2)

        # Call remove using product_name fallback
        from django.urls import reverse
        remove_url = reverse('remove_from_cart')
        response = self.client.delete(remove_url, {"product_name": "Lathe"}, content_type='application/json')
        self.assertEqual(response.status_code, 204)

        # Verify only 1 item remains in the cart, not 0!
        self.assertEqual(cart.items.count(), 1)


class ViewCartEmptyStateTests(TestCase):
    """
    M7 (регресс с живого стенда): корзина отвечала 404 после завершения заказа.

    OrderStateService.complete() гасит is_active у корзины — это правильно, но
    ViewCartView трактовал отсутствие активной корзины как «не найдено» и
    возвращал 404. Приложение показывало текст DioException вместо пустой
    корзины. Пустая корзина — валидное состояние, а не ошибка.
    """

    def setUp(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        self.user = CustomUser.objects.create_user(login='+79990000009', password='pw')
        refresh = RefreshToken.for_user(self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'

    def test_returns_empty_cart_when_there_is_no_active_one(self):
        # Корзина создаётся сигналом на регистрацию — гасим её, чтобы
        # воспроизвести состояние «заказ завершён, активной корзины нет».
        ShoppingCart.objects.filter(user=self.user).update(is_active=False)

        response = self.client.get('/api/cart/view_cart/')

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['basket'], [])
        self.assertEqual(body['total_cart_price'], 0)

    def test_returns_empty_cart_after_the_order_deactivated_it(self):
        cart = ShoppingCart.objects.create(user=self.user, is_active=True)
        cart.is_active = False
        cart.save(update_fields=['is_active'])

        response = self.client.get('/api/cart/view_cart/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['basket'], [])

    def test_existing_active_cart_is_reused_not_replaced(self):
        cart = ShoppingCart.objects.get(user=self.user, is_active=True)

        response = self.client.get('/api/cart/view_cart/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['cart_id'], cart.id)
        self.assertEqual(ShoppingCart.objects.filter(user=self.user, is_active=True).count(), 1)

    def test_two_active_carts_do_not_break_the_endpoint(self):
        """
        Уникальности активной корзины в БД нет, и прежний `.get(...)` на двух
        активных падал MultipleObjectsReturned — то есть 500 вместо корзины.
        """
        ShoppingCart.objects.create(user=self.user, is_active=True)
        newest = ShoppingCart.objects.create(user=self.user, is_active=True)

        response = self.client.get('/api/cart/view_cart/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['cart_id'], newest.id)
