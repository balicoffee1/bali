from celery import shared_task
from orders.models import Orders
import logging

logger = logging.getLogger(__name__)

@shared_task
def cancel_unpaid_order_task(order_id):
    try:
        order = Orders.objects.get(id=order_id)
        # Если заказ все еще не оплачен (не в статусе PAID) и не завершен/отменен
        if order.payment_status != Orders.PAID and order.status_orders not in [Orders.COMPLETED, Orders.CANCELED]:
            order.status_orders = Orders.CANCELED
            order.cancellation_reason = "Автоматическая отмена: заказ не был оплачен в течение 1.5 минут"
            order.save()
            logger.info(f"Заказ {order_id} автоматически отменен: не оплачен за 1.5 минуты.")
    except Orders.DoesNotExist:
        logger.warning(f"Задача автоматической отмены: заказ {order_id} не найден.")
