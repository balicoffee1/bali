"""Утверждённые подписи отправителя и проверка текущей настройки.

    python manage.py sms_senders

Подпись из ``SMS_SENDER`` обязана быть в этом списке со статусом ``active``:
иначе ``send.json`` отвечает ``sender address invalid``, приложение отдаёт
503, и выглядит это как отказ шлюза, а не как ошибка конфигурации.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from users import sms


class Command(BaseCommand):
    help = "Показывает подписи отправителя, утверждённые у SMS-провайдера."

    def handle(self, *args, **opts):
        if not sms.is_configured():
            raise CommandError(
                "SMS не настроены: проверьте SMS_ENABLED, SMS_LOGIN и "
                "SMS_PASSWORD в .env"
            )

        try:
            senders = sms.get_senders()
        except sms.SmsSendError as ex:
            raise CommandError(str(ex)) from ex

        if not senders:
            self.stdout.write(
                self.style.WARNING(
                    "У аккаунта нет ни одной подписи — сообщения уйдут с "
                    "номера провайдера"
                )
            )
            return

        current = settings.SMS_SENDER
        self.stdout.write(self.style.MIGRATE_HEADING("Подписи аккаунта:"))
        for sender in senders:
            name = sender.get("name")
            state = sender.get("status")
            mark = " ← SMS_SENDER" if name == current else ""
            line = f"  {name} — {state}{mark}"
            if state == "active":
                self.stdout.write(self.style.SUCCESS(line))
            else:
                self.stdout.write(self.style.WARNING(line))

        active = sms.active_sender_names()
        self.stdout.write("")

        if not current:
            self.stdout.write(
                self.style.WARNING(
                    "SMS_SENDER пуст — сообщения уйдут с номера провайдера."
                )
            )
        elif current in active:
            self.stdout.write(
                self.style.SUCCESS(f"SMS_SENDER = {current} — подпись активна")
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"SMS_SENDER = {current} — такой активной подписи у "
                    "аккаунта нет. Провайдер отклонит отправку с ответом "
                    "'sender address invalid'. Допустимые: "
                    + ", ".join(active)
                )
            )
