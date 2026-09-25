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
                              related_name="shifts", verbose_name="Сотрудник")
    start_time = models.DateTimeField(null=True, blank=True, verbose_name="Время начало")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="Время окончания")
    number_orders_closed = models.PositiveIntegerField(
        verbose_name="Закрытые заказы за смену",
        default=0)
    amount_closed_orders = models.DecimalField(
        verbose_name="Сумма заказов за смену",
        max_digits=10, decimal_places=2, default=0)
    status_shift = models.CharField(
        choices=Status, max_length=40, verbose_name="Статус смены"
    )

    def update_shift_statistics(self, save=True):
        from decimal import Decimal
        from django.db.models.functions import Coalesce
        from orders.models import Orders

        shop = self.staff.place_of_work if self.staff_id else None
        if shop:
            closed_orders = Orders.objects.filter(
                coffee_shop=shop,
                status_orders=Orders.COMPLETED,
            )
        else:
            closed_orders = Orders.objects.filter(
                staff=self.staff,
                status_orders=Orders.COMPLETED,
            )

        if self.start_time:
            closed_orders = closed_orders.filter(updated_at__gte=self.start_time)
        if self.end_time:
            closed_orders = closed_orders.filter(updated_at__lte=self.end_time)

        stats = closed_orders.aggregate(
            total_amount=Coalesce(models.Sum("full_price"), Decimal("0.00")),
            total_count=models.Count("id"),
        )

        self.amount_closed_orders = stats["total_amount"]
        self.number_orders_closed = stats["total_count"]
        if save:
            self.save(update_fields=["amount_closed_orders", "number_orders_closed"])


    class Meta:
        verbose_name = "Смена"
        verbose_name_plural = "Смены"
