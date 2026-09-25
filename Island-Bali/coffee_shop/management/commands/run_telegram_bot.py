import logging
import signal
import sys
import time
import requests
from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from coffee_shop.models import CoffeeShop
from reviews import telegram_bot

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Запуск Telegram-бота в режиме Long Polling для обработки команд и привязки кофеен."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = True

    def handle(self, *args, **options):
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        if not token:
            self.stderr.write(self.style.ERROR("TELEGRAM_BOT_TOKEN не задан в настройках."))
            return

        def handle_signal(sig, frame):
            self.stdout.write(self.style.WARNING(f"\nПолучен сигнал {sig}. Завершение работы бота..."))
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        self.stdout.write(self.style.SUCCESS("Telegram-бот запущен и слушает входящие сообщения (Long Polling)..."))

        session = requests.Session()
        offset = 0
        poll_url = f"https://api.telegram.org/bot{token}/getUpdates"

        while self.running:
            try:
                response = session.get(
                    poll_url,
                    params={"offset": offset, "timeout": 20},
                    timeout=(10, 30),
                )
                if response.status_code != 200:
                    logger.warning("Telegram getUpdates returned status %s: %s", response.status_code, response.text)
                    time.sleep(2)
                    continue

                data = response.json()
                if not data.get("ok"):
                    logger.warning("Telegram API error: %s", data)
                    time.sleep(2)
                    continue

                updates = data.get("result", [])
                for update in updates:
                    update_id = update.get("update_id", 0)
                    offset = max(offset, update_id + 1)
                    message = update.get("message")
                    if not message or "text" not in message:
                        continue

                    self.process_message(message)

            except requests.exceptions.RequestException as e:
                logger.warning("Сетевая ошибка при получении обновлений Telegram: %s", e)
                time.sleep(3)
            except Exception as e:
                logger.exception("Непредвиденная ошибка в цикле бота: %s", e)
                time.sleep(3)

        self.stdout.write(self.style.SUCCESS("Бот остановлен."))

    def process_message(self, message):
        chat_id = str(message["chat"]["id"])
        user = message.get("from", {})
        username = user.get("username", "")
        first_name = user.get("first_name", "пользователь")
        text = message.get("text", "").strip()

        logger.info("Входящее сообщение от %s (@%s): %s", chat_id, username, text)

        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1 and parts[1].startswith("bind_"):
                token = parts[1]
                self.handle_bind(chat_id, username, first_name, token)
            else:
                self.send_welcome_message(chat_id, first_name)
        elif text == "/help":
            self.send_help_message(chat_id)
        else:
            self.send_default_message(chat_id)

    def send_welcome_message(self, chat_id, first_name):
        msg = (
            f"👋 Привет, {first_name}!\n\n"
            f"Я официальный бот сети кофейных пространств Happy Island 🏝️\n\n"
            f"🆔 Ваш Telegram ID: {chat_id}\n\n"
            f"👉 Чтобы подключить получение отзывов по вашей кофейне, откройте "
            f"панель управления кофейней и нажмите кнопку «Подключить через Telegram», "
            f"либо введите ваш ID в настройках точки."
        )
        try:
            telegram_bot.send_review_to_user(chat_id, msg)
        except Exception as e:
            logger.error("Ошибка отправки приветствия: %s", e)

    def send_help_message(self, chat_id):
        msg = (
            "ℹ️ Этот бот предназначен для получения уведомлений об отзывах гостей "
            "и системных событиях кофеен Happy Island.\n\n"
            f"🆔 Ваш Telegram ID: {chat_id}\n\n"
            "Для привязки кофейни используйте кнопку в веб-панели управления."
        )
        try:
            telegram_bot.send_review_to_user(chat_id, msg)
        except Exception as e:
            logger.error("Ошибка отправки справки: %s", e)

    def send_default_message(self, chat_id):
        msg = (
            "🤖 Я автоматический бот-оповещатель Happy Island.\n"
            f"Ваш Telegram ID: {chat_id}\n\n"
            "Напишите /start для повторного вывода информации."
        )
        try:
            telegram_bot.send_review_to_user(chat_id, msg)
        except Exception as e:
            logger.error("Ошибка отправки сообщения: %s", e)

    def handle_bind(self, chat_id, username, first_name, token):
        cache_key = f"tg_bind_{token}"
        shop_id = cache.get(cache_key)

        if not shop_id:
            msg = (
                "⚠️ Ссылка для привязки устарела или уже была использована.\n\n"
                "Пожалуйста, откройте панель управления кофейней и нажмите "
                "«Подключить через Telegram» заново, чтобы получить свежую ссылку."
            )
            try:
                telegram_bot.send_review_to_user(chat_id, msg)
            except Exception as e:
                logger.error("Ошибка отправки сообщения об устаревшей ссылке: %s", e)
            return

        try:
            shop = CoffeeShop.objects.get(id=shop_id)
            shop.telegram_id = chat_id
            shop.telegram_username = f"@{username}" if username else first_name
            shop.save(update_fields=["telegram_id", "telegram_username"])

            # Удаляем временный токен и записываем статус привязки для веб-клиента
            cache.delete(cache_key)
            status_data = {
                "status": "linked",
                "shop_id": shop.id,
                "telegram_id": chat_id,
                "telegram_username": shop.telegram_username,
            }
            cache.set(f"tg_bind_status_{token}", status_data, timeout=300)

            shop_desc = f"{shop.street}, {shop.building_number}" if shop.street else str(shop)
            city_name = getattr(shop.city, "name", "") if shop.city else ""
            full_addr = f"{city_name}, {shop_desc}".strip(", ")

            success_msg = (
                f"✅ Кофейня успешно подключена к уведомлениям!\n\n"
                f"📍 Точка: {full_addr}\n\n"
                f"Теперь отзывы и оценки гостей этой кофейни будут приходить сюда в реальном времени."
            )
            telegram_bot.send_review_to_user(chat_id, success_msg)
            logger.info("Кофейня %s (ID %s) успешно привязана к Telegram %s (@%s)", full_addr, shop_id, chat_id, username)

        except CoffeeShop.DoesNotExist:
            telegram_bot.send_review_to_user(chat_id, "❌ Ошибка: привязываемая кофейня не найдена в базе данных.")
        except Exception as e:
            logger.exception("Ошибка при сохранении привязки кофейни: %s", e)
            telegram_bot.send_review_to_user(chat_id, "❌ Произошла ошибка при привязке. Попробуйте еще раз позже.")
