from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Orders

@receiver(post_save, sender=Orders)
def set_waiting_status_for_testing_order(sender, instance, created, **kwargs):
    if instance.is_testing:
        instance.status_orders = Orders.WAITING
        instance.payment_status = Orders.WAITING
        instance.save(update_fields=['status_orders', 'payment_status'])