from django.db import models

from cart.models import ShoppingCart
from coffee_shop.models import City, CoffeeShop
from staff.models import Staff
from users.models import CustomUser


class Orders(models.Model):
    StatusOrders = (
        ("Waiting", "Ожидание"),
        ("In Progress", "Выполняется"),
        ("Completed", "Выполнен"),
        ("Canceled", "Отменен")
    )
    PaymentStatus = (
        ("Pending", "Ожидание оплаты"),
        ("Paid", "Оплачено"),
        ("Failed", "Неудача")
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE,
                             related_name="user_orders",
                             verbose_name="Пользователь")
    city_choose = models.ForeignKey(City, related_name='city_choose',
                                    on_delete=models.CASCADE,
                                    verbose_name='Город в котором '
                                                 'заказывают кофе')
    coffee_shop = models.ForeignKey(CoffeeShop,
                                    related_name='coffee_shop_to_orders',
                                    verbose_name='Кофейня на улице',
                                    on_delete=models.CASCADE)
    cart = models.OneToOneField(ShoppingCart, on_delete=models.CASCADE,
                                verbose_name="Корзина пользователя")
    client_comments = models.TextField(blank=True, null=True,
                                       verbose_name='Комментарий клиента')
    staff_comments = models.TextField(blank=True, null=True,
                                      verbose_name='Комментарий сотрудника')
    time_is_finish = models.DateTimeField(blank=True, null=True,
                                          verbose_name='Время '
                                                       'до получения заказа')

    staff = models.ForeignKey(Staff, related_name='staff',
                              verbose_name="Исполнитель заказа",
                              on_delete=models.CASCADE)

    status_orders = models.CharField(choices=StatusOrders, max_length=30,
                                     verbose_name="Статус заказа")
    payment_status = models.CharField(choices=PaymentStatus, max_length=30,
                                      verbose_name="Статус оплаты")
    receipt_photo = models.ImageField(upload_to='order_receipts/',
                                      blank=True, null=True,
                                      verbose_name='Фото чека заказа')

    def __str__(self):
        return f'Заказ в {self.coffee_shop} от пользователя {self.user}'

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
