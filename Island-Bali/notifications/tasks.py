from celery import shared_task
from fcm_django.models import FCMDevice
from firebase_admin.messaging import Message
from firebase_admin.messaging import Notification as FcmAdmin


@shared_task
def send_notification_with_chats(**kwargs):
    data = kwargs.get('data')
    devices = FCMDevice.objects.filter(user=kwargs.get('user'), active=True)
    if devices:
        for device in devices:
            message = Message(
                notification=FcmAdmin(title=data['title'], body=data['body']),
            )
            device.send_message(message=message)


@shared_task
def send_firebase_push_notification(**kwargs):
    try:
        data = kwargs.get('data')
        user_id = kwargs.get('user')
        devices = FCMDevice.objects.filter(user=user_id, active=True)
        if devices.exists():
            for device in devices:
                device.send_message(Message(data=data))
    except Exception as e:
        # логгировать ошибку, например через sentry или logger
        print(f"Ошибка при отправке push: {e}")
