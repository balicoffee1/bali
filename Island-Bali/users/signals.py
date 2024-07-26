from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver

User = get_user_model()


@receiver(pre_save, sender=User)
def check_owner_exists(sender, instance, **kwargs):
    if instance.role == "owner":
        existing_owner = User.objects.filter(role="owner").first()

        if existing_owner and existing_owner != instance:
            raise Exception(
                "Владелец уже существует. Создание нового владельца отменено."
            )
