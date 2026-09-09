import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_franchise_notification_sync(instance):
    """
    Синхронная отправка письма о новой заявке на франшизу.
    Ошибки отправки логируются и не приводят к падению запроса (fail_silently=True).
    """
    try:
        from_email = getattr(settings, "EMAIL_HOST_USER", None)
        if not from_email:
            logger.warning("EMAIL_HOST_USER не настроен, отправка email по франшизе пропущена.")
            return

        recipients = getattr(
            settings,
            "FRANCHISE_NOTIFICATION_EMAILS",
            ["tima.j.zh@gmail.com"],
        )

        message = (
            f"Новая заявка на франшизу #{instance.id}\n\n"
            f"ФИО: {instance.name}\n"
            f"Номер телефона: {instance.number_phone}\n"
            f"Пожелания / контакты: {instance.text}\n"
            f"Дата заявки: {instance.created_at}\n"
        )

        send_mail(
            subject=f"Заявка на франшизу #{instance.id} от {instance.name}",
            message=message,
            from_email=from_email,
            recipient_list=recipients,
            fail_silently=True,
        )
        logger.info(f"Уведомление по заявке на франшизу #{instance.id} отправлено.")
    except Exception as e:
        logger.exception(f"Ошибка при отправке email о заявке на франшизу #{instance.id}: {e}")


def send_franchise_notification(instance):
    """
    Пытается поставить отправку уведомления в очередь Celery.
    Если Celery недоступен, безопасно отправляет синхронно без сбоя для пользователя.
    """
    try:
        from .tasks import send_franchise_notification_task
        send_franchise_notification_task.delay(instance.id)
    except Exception as e:
        logger.warning(f"Не удалось поставить задачу Celery в очередь ({e}), отправляем синхронно.")
        send_franchise_notification_sync(instance)


def send_reset_password(text: str):
    """Устаревший метод для обратной совместимости."""
    try:
        from_email = getattr(settings, "EMAIL_HOST_USER", None)
        send_mail(
            subject="Заявка на франшизу",
            message=str(text),
            from_email=from_email,
            recipient_list=["tima.j.zh@gmail.com"],
            fail_silently=True,
        )
    except Exception as e:
        logger.exception(f"Ошибка в устаревшем send_reset_password: {e}")