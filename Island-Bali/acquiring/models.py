from django.db import models
from orders.models import Orders

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('created', 'Created'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    order = models.OneToOneField(
        Orders, on_delete=models.CASCADE, related_name="payment", verbose_name="Заказ"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Сумма оплаты")
    status = models.CharField(max_length=50, choices=PAYMENT_STATUS_CHOICES, default='created', verbose_name="Статус оплаты")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    payment_data = models.JSONField(null=True, blank=True, verbose_name="Данные платежа")

    def __str__(self):
        return f"Payment for Order {self.order.id} - {self.status}"

    class Meta:
        verbose_name = "Оплата"
        verbose_name_plural = "Оплаты"
        ordering = ['-created_at']