from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Staff

User = get_user_model()


@receiver(pre_save, sender=Staff)
def check_owner_exists(sender, instance, **kwargs):
    user = User.objects.filter(login=instance.users.login).first()
    if user.role == "user":
        user.role = 'employee'
        user.save()
