from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Orders
from orders.tasks import cancel_unpaid_order_task

@receiver(post_save, sender=Orders)
def set_waiting_status_for_testing_order(sender, instance, created, **kwargs):
    if instance.is_testing:
        instance.status_orders = Orders.WAITING
        instance.payment_status = Orders.WAITING
        instance.save(update_fields=['status_orders', 'payment_status'])

@receiver(post_save, sender=Orders)
def schedule_order_timeout(sender, instance, created, **kwargs):
    if created:
        # Планируем отмену через 90 секунд (1.5 минуты)
        cancel_unpaid_order_task.apply_async(args=[instance.id], countdown=90)