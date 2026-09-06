"""Celery-задачи отправки push-уведомлений через FCM.

Отправка идёт одним multicast-вызовом на все устройства пользователя:
FCMDevice.objects.filter(...).send_message() в fcm-django 3.x сам разбирает
ответ FCM и гасит (active=False) токены, на которые FCM вернул UNREGISTERED.
Ручной цикл по устройствам, который был здесь раньше, этого не делал — мёртвые
токены копились навсегда.
"""
import logging

from celery import shared_task
from fcm_django.models import FCMDevice
from firebase_admin.messaging import AndroidConfig, AndroidNotification, APNSConfig, APNSPayload, Aps
from firebase_admin.messaging import Message
from firebase_admin.messaging import Notification as FcmNotification

logger = logging.getLogger(__name__)

# Канал должен существовать в приложении (создаётся в NotificationRepository.init).
ANDROID_CHANNEL_ID = "happy_island_channel"


def deliver_push(*, user_id, title, body, data=None):
    """Синхронная отправка. Отдельно от задачи, чтобы её можно было вызвать
    напрямую (management-команда, тесты) и увидеть исключение как есть, без
    обёртки Celery retry."""
    devices = FCMDevice.objects.filter(user_id=user_id, active=True)
    if not devices.exists():
        logger.info("push_skipped_no_devices user_id=%s", user_id)
        return None

    payload = {str(k): str(v) for k, v in (data or {}).items()}
    # click_action нужен Android, чтобы тап по пушу открыл MainActivity, а не
    # просто снял уведомление.
    payload.setdefault("click_action", "FLUTTER_NOTIFICATION_CLICK")

    message = Message(
        notification=FcmNotification(title=title, body=body),
        data=payload,
        android=AndroidConfig(
            priority="high",
            notification=AndroidNotification(
                channel_id=ANDROID_CHANNEL_ID,
                # Иконку и цвет Android берёт из meta-data манифеста приложения.
                click_action="FLUTTER_NOTIFICATION_CLICK",
            ),
        ),
        apns=APNSConfig(
            headers={"apns-priority": "10"},
            payload=APNSPayload(aps=Aps(sound="default")),
        ),
    )

    result = devices.send_message(message)
    logger.info(
        "push_sent user_id=%s sent=%s success=%s failure=%s deactivated=%s",
        user_id,
        len(result.registration_ids_sent),
        result.success_count,
        result.failure_count,
        len(result.deactivated_registration_ids),
    )
    if result.all_failed:
        # Ни одно устройство не приняло сообщение: это не «нет подписчиков»,
        # а симптом конфигурации (протухший service account, чужой APNs-ключ).
        logger.error(
            "push_all_failed user_id=%s failed=%s",
            user_id,
            len(result.failed_registration_ids),
        )
    return result


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    retry_jitter=True,
)
def send_firebase_push_notification(*, user_id, title, body, data=None):
    deliver_push(user_id=user_id, title=title, body=body, data=data)
