from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Staff

User = get_user_model()


@receiver(pre_save, sender=Staff)
def check_owner_exists(sender, instance, **kwargs):
    user = getattr(instance, "users", None)
    if user is None and getattr(instance, "users_id", None):
        user = User.objects.filter(id=instance.users_id).first()
    if user and getattr(user, "role", None) == "user":
        user.role = "employee"
        user.save(update_fields=["role"])
