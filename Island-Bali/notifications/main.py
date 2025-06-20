from .tasks import send_firebase_push_notification


def send_push_notification(user, title, body):

    if user.has_device():
        data = {
            "title": title,
            "body": body,
            "content": str(user.id),
            "sender": str(user.id),
            "type": "Новые сообщения",
        }

        send_firebase_push_notification.delay(user=user.id, data=data)