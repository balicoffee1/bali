from django.db.models.signals import post_save
from django.dispatch import receiver
from users.models import CustomUser
from .models import ShoppingCart

@receiver(post_save, sender=CustomUser)
def create_user_cart(sender, instance, created, **kwargs):
    if created:
        ShoppingCart.objects.create(user=instance, is_active=True)