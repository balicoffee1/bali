"""Фоновые задачи вокруг SMS-шлюза iqsms.

Две штуки, которых раньше не было вовсе:

* ``check_sms_delivery`` — спрашивает у провайдера, дошли ли отправленные
  коды. Без этого на жалобу «код не приходит» ответить было нечем.
* ``notify_low_sms_balance`` — предупреждает, пока деньги не кончились.
  В реестре доступов на этот счёт записано «отслеживать баланс 1 раз/мес»,
  то есть вручную; при пустом счёте вход в приложение встаёт для всех.
"""

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from loguru import logger

from . import sms
from .models import PhoneVerification

# Обычный sendMessage Telegram Bot API, просто живёт в приложении отзывов.
from reviews.telegram_bot import send_review_to_user as send_telegram_message


@shared_task(
    autoretry_for=(sms.SmsSendError,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def check_sms_delivery():
    """Обновляет статус доставки у сообщений, по которым он ещё не финальный.

    Опрашиваются только записи с непустым ``smsc_id``, у которых статус пуст
    или промежуточный (``queued``, ``smsc submit``), и не старше
    ``SMS_STATUS_MAX_AGE_HOURS``: код живёт пять минут, и через сутки его
    судьба уже никого не интересует.
    """
    if not sms.is_configured():
        return "SMS отключены"

    horizon = timezone.now() - timedelta(hours=settings.SMS_STATUS_MAX_AGE_HOURS)

    pending = list(
        PhoneVerification.objects
        .filter(created_at__gte=horizon)
        .exclude(smsc_id="")
        .exclude(delivery_status__in=sms.DELIVERY_FINAL_STATUSES)
        .order_by("-created_at")[:sms.MAX_MESSAGES_PER_REQUEST]
    )
    if not pending:
        return "Нечего проверять"

    statuses = sms.check_status([item.smsc_id for item in pending])
    if not statuses:
        return "Провайдер не вернул статусов"

    now = timezone.now()
    updated = []
    for item in pending:
        status_ = statuses.get(item.smsc_id)
        if not status_:
            continue
        item.delivery_status = status_
        item.status_checked_at = now
        updated.append(item)

        if status_ in (sms.DELIVERY_SMSC_REJECT, sms.DELIVERY_ERROR):
            logger.warning(
                "SMS с кодом не доставлена: {} (smscId {}), статус {}",
                item.phone, item.smsc_id, status_,
            )

    if updated:
        PhoneVerification.objects.bulk_update(
            updated, ["delivery_status", "status_checked_at"]
        )

    return f"Обновлено статусов: {len(updated)}"


@shared_task(
    autoretry_for=(sms.SmsSendError,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def notify_low_sms_balance():
    """Предупреждает в Telegram, когда на счёте провайдера мало денег."""
    if not sms.is_configured():
        return "SMS отключены"

    balance = sms.rub_balance()
    if balance is None:
        logger.warning("Провайдер не вернул рублёвый баланс")
        return "Баланс не получен"

    if balance >= settings.SMS_BALANCE_MIN:
        logger.info("Баланс SMS: {} ₽", balance)
        return f"Баланс в норме: {balance} ₽"

    text = (
        f"Happy Island: на счёте SMS осталось {balance:.2f} ₽ "
        f"(порог {settings.SMS_BALANCE_MIN:.0f} ₽).\n"
        "Когда деньги закончатся, коды подтверждения перестанут уходить и "
        "новые пользователи не смогут войти в приложение.\n"
        "Пополнить: https://web.iqsms.ru (минимальная сумма 3000 ₽)."
    )
    logger.error("Низкий баланс SMS: {} ₽", balance)

    chat_id = settings.SMS_BALANCE_ALERT_CHAT_ID
    if not chat_id:
        # Получателя не задали — предупреждение остаётся в логе. Молча
        # игнорировать нельзя: это единственный сигнал до отказа отправки.
        logger.warning(
            "SMS_BALANCE_ALERT_CHAT_ID не задан, предупреждение о балансе "
            "никому не отправлено"
        )
        return f"Низкий баланс: {balance} ₽ (получатель не задан)"

    send_telegram_message(chat_id=chat_id, review_text=text)
    return f"Низкий баланс: {balance} ₽, предупреждение отправлено"
