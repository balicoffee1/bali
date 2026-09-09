import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def send_franchise_notification_task(franchise_request_id: int):
    """
    Асинхронная задача Celery для отправки email-уведомления о новой заявке на франшизу.
    """
    from .models import FranchiseRequest
    from .utils import send_franchise_notification_sync

    try:
        instance = FranchiseRequest.objects.get(pk=franchise_request_id)
        send_franchise_notification_sync(instance)
    except FranchiseRequest.DoesNotExist:
        logger.warning(
            f"FranchiseRequest #{franchise_request_id} не найден в базе данных."
        )
