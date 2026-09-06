from decimal import Decimal

from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from bonus_system.services import calculate_cart_pricing, get_loyalty_status
from cart.models import CartItem, ShoppingCart, get_active_cart
from coffee_shop.models import Acquiring, City, CoffeeShop, CrmSystem
from menu_coffee_product.models import Category, Product
from orders.models import Orders
from users.models import CustomUser


class ServerLoyaltyTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            login="+79991112233", password="password123"
        )
        self.city = City.objects.create(name="Moscow")
        crm = CrmSystem.objects.create(name="QuickRestoApi")
        acquiring = Acquiring.objects.create(
            for_coffeeshop="Test",
            name="RussianStandart",
            login="login",
            password="password",
        )
        self.shop = CoffeeShop.objects.create(
            city=self.city,
            street="Arbat",
            building_number="1",
            email="shop@test.com",
            telegram_username="@shop",
            crm_system=crm,
            acquiring=acquiring,
        )
        category = Category.objects.create(coffee_shop=self.shop, name="Coffee")
        self.product = Product.objects.create(
            coffee_shop=self.shop,
            category=category,
            product="Latte",
            price_s=Decimal("1000.00"),
            price_m=Decimal("1000.00"),
            price_l=Decimal("1000.00"),
            product_type="coffee",
        )

        self.cart = get_active_cart(self.user)
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            amount=1,
            size=CartItem.SizeChoices.S,
        )

        refresh = RefreshToken.for_user(self.user)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {refresh.access_token}"

    def make_completed_order(self, price, **overrides):
        past_cart = ShoppingCart.objects.create(user=self.user, is_active=False)
        values = {
            "user": self.user,
            "city_choose": self.city,
            "coffee_shop": self.shop,
            "cart": past_cart,
            "status_orders": Orders.COMPLETED,
            "payment_status": Orders.PAID,
            "full_price": Decimal(price),
        }
        values.update(overrides)
        return Orders.objects.create(**values)

    def test_only_completed_non_test_orders_count_toward_discount(self):
        self.make_completed_order("3000.00")
        self.make_completed_order("2000.00")
        self.make_completed_order("9000.00", status_orders=Orders.CANCELED)
        testing_order = self.make_completed_order("9000.00")
        Orders.objects.filter(pk=testing_order.pk).update(is_testing=True)

        status = get_loyalty_status(self.user)

        self.assertEqual(status.qualifying_spend, Decimal("5000.00"))
        self.assertEqual(status.remaining, Decimal("0.00"))
        self.assertEqual(status.discount_percent, Decimal("5.00"))
        self.assertTrue(status.is_eligible)

    def test_cart_price_is_calculated_on_server(self):
        self.make_completed_order("5000.00")

        pricing = calculate_cart_pricing(self.user, self.cart)

        self.assertEqual(pricing.subtotal, Decimal("1000.00"))
        self.assertEqual(pricing.discount_amount, Decimal("50.00"))
        self.assertEqual(pricing.total, Decimal("950.00"))

    def test_cart_has_no_discount_before_threshold(self):
        pricing = calculate_cart_pricing(self.user, self.cart)

        self.assertEqual(pricing.subtotal, Decimal("1000.00"))
        self.assertEqual(pricing.discount_percent, Decimal("0.00"))
        self.assertEqual(pricing.discount_amount, Decimal("0.00"))
        self.assertEqual(pricing.total, Decimal("1000.00"))

    def test_order_endpoint_ignores_client_price_and_saves_pricing_snapshot(self):
        self.make_completed_order("5000.00")

        response = self.client.post(
            "/api/orders/orders/",
            {
                "city_choose": self.city.id,
                "coffee_shop": self.shop.id,
                "client_comments": "",
                "full_price": "1.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        order = Orders.objects.get(pk=response.data["id"])
        self.assertEqual(order.subtotal_price, Decimal("1000.00"))
        self.assertEqual(order.discount_percent, Decimal("5.00"))
        self.assertEqual(order.discount_amount, Decimal("50.00"))
        self.assertEqual(order.full_price, Decimal("950.00"))
        self.assertTrue(order.is_used_discount)

    def test_loyalty_endpoint_returns_server_progress(self):
        self.make_completed_order("1250.00")

        response = self.client.get("/api/bonus_system/loyalty/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(str(response.data["progress"])), Decimal("1250.00"))
        self.assertEqual(Decimal(str(response.data["remaining"])), Decimal("3750.00"))
        self.assertFalse(response.data["is_eligible"])
