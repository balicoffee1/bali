from django.db import models
from django.db.models import Sum

from coffee_shop.models import CoffeeShop
from users.models import CustomUser


class Staff(models.Model):
    users = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="staff",
        verbose_name="Пользователь",
    )

    place_of_work = models.ForeignKey(
        CoffeeShop,
        on_delete=models.CASCADE,
        related_name="staff",
        verbose_name="Место работы",
        null=True,
    )

    def get_staff_details(self):
        """Метод для получения детальной информации о сотруднике."""
        return {
            "full_name": f"{self.users.first_name} {self.users.last_name}",
            "email": self.users.email,
            "place_of_work": self.place_of_work.city if self.place_of_work
            else None,
            # Другие поля, которые вы хотите включить
        }

    def __str__(self):
        return self.users.first_name

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"


class Shift(models.Model):
    Status = (
        ("Open", "Смена открыта"),
        ("Closed", "Смена закрыта"),
    )
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE,
                              related_name="shifts")
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    number_orders_closed = models.PositiveIntegerField(
        verbose_name="Закрытые заказы за смену",
        default=0)
    amount_closed_orders = models.DecimalField(
        verbose_name="Сумма заказов за смену",
        max_digits=10, decimal_places=2, default=0)
    status_shift = models.CharField(
        choices=Status, max_length=40, verbose_name="Статус смены"
    )

    def update_shift_statistics(self):
        from orders.models import Orders

        closed_orders = Orders.objects.filter(
            staff=self.staff,
            status_orders="Completed",
            time_is_finish__range=(self.start_time, self.end_time)
        )

        total_amount = closed_orders.aggregate(
            total_amount=Sum('menu_items__price'))['total_amount'] or 0

        self.amount_closed_orders = total_amount
        self.number_orders_closed = closed_orders.count()
        self.save()

    class Meta:
        verbose_name = "Смена"
        verbose_name_plural = "Смены"
