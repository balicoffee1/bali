"""Остаток на счёте SMS-провайдера.

    python manage.py sms_balance
    python manage.py sms_balance --quiet   # только число, для скриптов
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from users import sms


class Command(BaseCommand):
    help = "Показывает баланс аккаунта у SMS-провайдера (iqsms)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Вывести только рублёвый остаток без пояснений.",
        )

    def handle(self, *args, **opts):
        if not sms.is_configured():
            raise CommandError(
                "SMS не настроены: проверьте SMS_ENABLED, SMS_LOGIN и "
                "SMS_PASSWORD в .env"
            )

        try:
            entries = sms.get_balance()
        except sms.SmsSendError as ex:
            raise CommandError(str(ex)) from ex

        rub = None
        for entry in entries:
            if str(entry.get("type", "")).upper() == "RUB":
                try:
                    rub = float(entry.get("balance"))
                except (TypeError, ValueError):
                    rub = None

        if opts["quiet"]:
            self.stdout.write(str(rub if rub is not None else ""))
            return

        if not entries:
            self.stdout.write(self.style.WARNING("Провайдер не вернул баланс"))
            return

        self.stdout.write(self.style.MIGRATE_HEADING("Баланс аккаунта:"))
        for entry in entries:
            self.stdout.write(
                f"  {entry.get('type')}: {entry.get('balance')} "
                f"(кредит {entry.get('credit')})"
            )

        if rub is None:
            return

        threshold = settings.SMS_BALANCE_MIN
        if rub < threshold:
            self.stdout.write(
                self.style.ERROR(
                    f"\nМало денег: {rub:.2f} ₽ при пороге {threshold:.0f} ₽. "
                    "Когда счёт опустеет, коды подтверждения перестанут "
                    "уходить и вход в приложение остановится. "
                    "Пополнение у провайдера — от 3000 ₽."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\nБаланс в норме (порог {threshold:.0f} ₽)")
            )
