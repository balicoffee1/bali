from django.db import models

from menu_coffee_product.models import Product, Addon
from users.models import CustomUser


class ShoppingCart(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="cart", null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True, verbose_name="Активна ли корзина")

    class Meta:
        ordering = ['id']
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"

    def __str__(self):
        return f"Корзина пользователя: {self.user}"

    @property
    def cart_total_price(self):
        """Высчитывает полную стоимость корзины."""
        total_price = sum(item.item_total_price for item in self.items.all())
        return round(total_price, 2)

    def send_orders_for_confirmation_to_barista(self, user, city_choose,
                                                coffee_shop, client_comments,
                                                staff, time_is_finish, cart):
        """
        Метод для создания нового заказа и связывания его с текущей корзиной.
        """
        from orders.models import Orders
        order = Orders.objects.create(
            user=user,
            city_choose=city_choose,
            coffee_shop=coffee_shop,
            cart=cart,
            client_comments=client_comments,
            status_orders="Waiting",
            payment_status="Pending"
        )

        self.order = order
        self.save()

        return order


class CartItem(models.Model):
    class SizeChoices(models.TextChoices):
        S = "S", "Small"
        M = "M", "Medium"
        L = "L", "Large"
    cart = models.ForeignKey(
        ShoppingCart, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        Product, related_name="cart_items", on_delete=models.CASCADE,
        null=True, blank=True, verbose_name="Продукт"
    )
    addons = models.ManyToManyField(Addon, related_name='cart_items', blank=True, verbose_name="Добавки")
    flavors = models.ManyToManyField(
        'menu_coffee_product.AdditiveFlavors',
        related_name='cart_items',
        blank=True,
        verbose_name="Вкусовые добавки"
    )
    amount = models.PositiveIntegerField(default=0, verbose_name="Колличество")
    size = models.CharField(
        max_length=1,
        choices=SizeChoices.choices,
        default=SizeChoices.S,
        verbose_name="Размер"
    )

    class Meta:
        ordering = ['id']
        verbose_name = "Продукт в корзине"
        verbose_name_plural = "Продукты в корзине"
        constraints = [
            models.UniqueConstraint(
                fields=('cart', 'product'),
                name='unique_cart_product'
            )
        ]

    def __str__(self):
        return (f"Продукт {self.product.product} в "
                f"корзине пользователя: {self.cart.user}")

    @property
    def item_total_price(self):
        size_prices = {
            self.SizeChoices.S: self.product.price_s,
            self.SizeChoices.M: self.product.price_m,
            self.SizeChoices.L: self.product.price_l
        }
        product_price = size_prices.get(self.size)
        
        addons_price = sum(addon.price for addon in self.addons.all())
        
        return (product_price + addons_price) * self.amount
