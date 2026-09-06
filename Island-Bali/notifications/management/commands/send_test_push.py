"""Ручная проверка сквозного пути доставки пуша.

Отправляет синхронно (без Celery), чтобы ошибки FCM были видны сразу в консоли,
а не в логе воркера. Пример:

    docker compose exec web python manage.py send_test_push --phone +79991234567
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from fcm_django.models import FCMDevice

from notifications.tasks import deliver_push

User = get_user_model()


class Command(BaseCommand):
    help = "Отправить тестовый push конкретному пользователю (синхронно)."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--user-id", type=int)
        group.add_argument("--phone", type=str, help="phone_number или login")
        parser.add_argument("--title", default="Тестовый push")
        parser.add_argument("--body", default="Если вы это видите — доставка работает")

    def handle(self, *args, **options):
        user = self._resolve_user(options)

        devices = FCMDevice.objects.filter(user=user)
        active = devices.filter(active=True)
        self.stdout.write(
            f"Пользователь #{user.id}: устройств всего {devices.count()}, активных {active.count()}"
        )
        for device in devices:
            self.stdout.write(
                f"  - {device.type or '?':8} active={device.active} "
                f"token=...{device.registration_id[-12:]}"
            )
        if not active.exists():
            raise CommandError(
                "Нет активных устройств. Приложение не зарегистрировало FCM-токен — "
                "проверьте POST /api/users/fcm/register/."
            )

        # Прямой вызов, минуя брокер: нужен немедленный, видимый результат.
        result = deliver_push(
            user_id=user.id,
            title=options["title"],
            body=options["body"],
            data={"type": "test"},
        )
        if result is None:
            raise CommandError("Отправка не выполнялась: активных устройств нет.")

        # Печатаем итог здесь, а не полагаемся на логгер: у management-команды
        # его вывод в консоль обычно не настроен, и «отправлено» без цифр не
        # отличает успех от отказа FCM.
        self.stdout.write(
            f"Отправлено на токенов: {len(result.registration_ids_sent)}, "
            f"успешно: {result.success_count}, с ошибкой: {result.failure_count}, "
            f"деактивировано: {len(result.deactivated_registration_ids)}"
        )
        for response in getattr(result.response, "responses", []):
            if not response.success:
                error = response.exception
                self.stdout.write(
                    self.style.ERROR(
                        f"  {type(error).__name__} "
                        f"[{getattr(error, 'code', '—')}]: {error}"
                    )
                )

        if result.failure_count:
            raise CommandError(
                "FCM отклонил часть сообщений — см. ошибки выше. Частые причины: "
                "протухший service account или несоответствие APNs-окружения "
                "(sandbox против production)."
            )
        self.stdout.write(self.style.SUCCESS("Доставлено в FCM."))

    @staticmethod
    def _resolve_user(options):
        if options["user_id"]:
            try:
                return User.objects.get(pk=options["user_id"])
            except User.DoesNotExist:
                raise CommandError(f"Пользователь {options['user_id']} не найден")

        phone = options["phone"]
        user = User.objects.filter(phone_number=phone).first() or User.objects.filter(login=phone).first()
        if user is None:
            raise CommandError(f"Пользователь с телефоном/логином {phone} не найден")
        return user
