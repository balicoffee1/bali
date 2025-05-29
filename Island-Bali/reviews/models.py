from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from coffee_shop.models import CoffeeShop
from orders.models import Orders
from users.models import CustomUser


class ReviewsCoffeeShop(models.Model):
    coffee_shop = models.ForeignKey(CoffeeShop, on_delete=models.CASCADE,
                                    verbose_name="Кофейня, в которой "
                                                 "был сделан заказ")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE,
                             verbose_name="Пользователь, оставивший отзыв")
    orders = models.OneToOneField(Orders, on_delete=models.CASCADE,
                                  verbose_name="Заказ, к которому "
                                               "оставлен отзыв", related_name='review')
    evaluation = models.IntegerField(
        verbose_name="Оценка заказа",
        help_text="Оцените заказ от 1 до 5",
        validators=[MinValueValidator(1,
                                      message="Оценка должна быть не менее 1"),
                    MaxValueValidator(5,
                                      message="Оценка должна "
                                              "быть не более 5")],
    )
    very_tasty = models.BooleanField(verbose_name="Блюда очень вкусные",
                                     default=False)
    wide_range = models.BooleanField(verbose_name="Широкий ассортимент",
                                     default=False)
    nice_prices = models.BooleanField(verbose_name="Приемлемые цены",
                                      default=False)
    comments = models.CharField(
        verbose_name="Комментарий после выполненного заказа",
        help_text="Оставьте ваш комментарий",
        max_length=250,
        blank=True
    )

    def __str__(self):
        return f"с оценкой {self.evaluation}"

    def get_coffeeshop_email(self):
        return self.coffee_shop.email

    def get_coffee_shop_telegram(self):
        return self.coffee_shop.telegram_username

    class Meta:
        verbose_name = "Отзыв пользователя"
        verbose_name_plural = "Отзывы пользователей"
