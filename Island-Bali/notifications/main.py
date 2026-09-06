"""Точка входа для отправки пушей из бизнес-кода.

Единственная публичная функция — send_push_notification(). Она не ходит в FCM
сама: ставит задачу в Celery и возвращает управление немедленно, чтобы отказ
брокера или FCM никогда не влиял на латентность и код ответа API.
"""
import logging

from .tasks import send_firebase_push_notification

logger = logging.getLogger(__name__)


def send_push_notification(user, title, body, *, order_id=None, event=None):
    """Поставить пуш в очередь.

    order_id/event попадают в data-payload, чтобы приложение по тапу могло
    открыть диалог статуса нужного заказа, а не просто главный экран.
    """
    if user is None:
        return

    # Раньше здесь стоял user.has_device() — лишний SELECT, который к тому же
    # не фильтровал active=True и потому расходился с выборкой в самой задаче.
    # Проверку делает task: она всё равно обязана выбрать устройства.
    data = {"type": event or "message"}
    if order_id is not None:
        data["order_id"] = str(order_id)

    try:
        send_firebase_push_notification.delay(
            user_id=user.id, title=title, body=body, data=data
        )
    except Exception:
        # Недоступный брокер не должен ронять HTTP-ручку, из которой пуш шлётся
        # побочным эффектом (принятие/отмена/готовность заказа).
        logger.exception("push_enqueue_failed user_id=%s event=%s", user.id, event)
