"""Статус доставки отправленных кодов подтверждения.

    python manage.py sms_status --phone +79991234567
    python manage.py sms_status --smsc-id A132571BC
    python manage.py sms_status --recent 20

Отвечает на вопрос «код не пришёл»: сообщение не дошло до абонента или
пользователь его просто не ввёл.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from users import sms
from users.models import PhoneVerification
from users.utils import normalize_phone


class Command(BaseCommand):
    help = "Спрашивает у провайдера статус доставки отправленных SMS."

    def add_arguments(self, parser):
        parser.add_argument("--phone", help="Номер телефона получателя")
        parser.add_argument("--smsc-id", dest="smsc_id", help="Идентификатор у провайдера")
        parser.add_argument(
            "--recent",
            type=int,
            default=10,
            help="Сколько последних сообщений проверить, если не заданы "
                 "--phone и --smsc-id (по умолчанию 10).",
        )

    def handle(self, *args, **opts):
        if not sms.is_configured():
            raise CommandError(
                "SMS не настроены: проверьте SMS_ENABLED, SMS_LOGIN и "
                "SMS_PASSWORD в .env"
            )

        queryset = PhoneVerification.objects.exclude(smsc_id="")

        if opts["smsc_id"]:
            queryset = queryset.filter(smsc_id=opts["smsc_id"])
        elif opts["phone"]:
            queryset = queryset.filter(phone__contains=normalize_phone(opts["phone"])[-10:])

        limit = min(opts["recent"], sms.MAX_MESSAGES_PER_REQUEST)
        items = list(queryset.order_by("-created_at")[:limit])

        if not items:
            self.stdout.write(
                self.style.WARNING(
                    "Подходящих сообщений не найдено. Записи с smscId "
                    "появляются только у кодов, отправленных после перехода "
                    "на новый клиент провайдера."
                )
            )
            return

        try:
            statuses = sms.check_status([item.smsc_id for item in items])
        except sms.SmsSendError as ex:
            raise CommandError(str(ex)) from ex

        now = timezone.now()
        updated = []

        self.stdout.write(self.style.MIGRATE_HEADING("Статусы доставки:"))
        for item in items:
            status_ = statuses.get(item.smsc_id) or "нет ответа"
            age = int((now - item.created_at).total_seconds() // 60)
            line = (
                f"  {item.phone}  smscId {item.smsc_id}  "
                f"{age} мин назад  →  {status_}"
            )

            if status_ == sms.DELIVERY_DELIVERED:
                self.stdout.write(self.style.SUCCESS(line))
            elif status_ in (sms.DELIVERY_SMSC_REJECT, sms.DELIVERY_ERROR):
                self.stdout.write(self.style.ERROR(line))
            else:
                self.stdout.write(line)

            if statuses.get(item.smsc_id):
                item.delivery_status = status_
                item.status_checked_at = now
                updated.append(item)

        if updated:
            PhoneVerification.objects.bulk_update(
                updated, ["delivery_status", "status_checked_at"]
            )
            self.stdout.write(
                self.style.SUCCESS(f"\nСохранено статусов: {len(updated)}")
            )
