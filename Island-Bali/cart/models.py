from django.db import models

from menu_coffee_product.models import Product
from users.models import CustomUser


class ShoppingCart(models.Model):
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="cart", null=True,
        blank=True
    )
    is_active = models.BooleanField(default=False)

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
            staff=staff,
            time_is_finish=time_is_finish,
            status_orders="Waiting",
            payment_status="Pending"
        )

        self.order = order
        self.save()

        return order


class CartItem(models.Model):
    cart = models.ForeignKey(
        ShoppingCart, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        Product, related_name="cart_items", on_delete=models.CASCADE
    )
    amount = models.PositiveIntegerField(default=0)

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
        """Высчитывает полную стоимость продукта в корзине."""
        return round(self.product.price * self.amount, 2)
