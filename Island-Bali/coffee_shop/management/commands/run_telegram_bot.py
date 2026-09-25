import html
import json
import logging
import signal
import sys
import time
from decimal import Decimal

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from coffee_shop.models import CoffeeShop
from orders.models import Orders
from reviews.models import ReviewsCoffeeShop
from staff.models import Shift
from reviews import telegram_bot

logger = logging.getLogger(__name__)

MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": "💬 История отзывов"}, {"text": "📦 История заказов"}],
        [{"text": "📊 Сводка за сегодня"}, {"text": "⏱ Текущая смена"}],
        [{"text": "📍 Мои кофейни"}],
    ],
    "resize_keyboard": True,
}


class Command(BaseCommand):
    help = "Запуск Telegram-бота в режиме Long Polling для обработки команд, меню и привязки кофеен."

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

                    if "message" in update:
                        message = update["message"]
                        if "text" in message:
                            self.process_message(message)
                    elif "callback_query" in update:
                        self.process_callback_query(update["callback_query"])

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
            if len(parts) > 1 and parts[1].strip().startswith("bind_"):
                token = parts[1].strip()
                self.handle_bind(chat_id, username, first_name, token)
            else:
                self.send_welcome_message(chat_id, first_name)
        elif text in ["/help", "помощь", "help"]:
            self.send_help_message(chat_id)
        elif text in ["💬 История отзывов", "/reviews", "отзывы"]:
            self.handle_reviews(chat_id, offset=0)
        elif text in ["📦 История заказов", "/orders", "заказы"]:
            self.handle_orders(chat_id, offset=0)
        elif text in ["📊 Сводка за сегодня", "/today", "сводка"]:
            self.handle_today_summary(chat_id)
        elif text in ["⏱ Текущая смена", "/shift", "смена"]:
            self.handle_current_shift(chat_id)
        elif text in ["📍 Мои кофейни", "/shops", "кофейни"]:
            self.handle_my_shops(chat_id)
        else:
            self.send_default_message(chat_id)

    def process_callback_query(self, callback_query):
        query_id = callback_query.get("id")
        from_user = callback_query.get("from", {})
        chat_id = str(from_user.get("id"))
        data = callback_query.get("data", "")

        try:
            telegram_bot.answer_callback_query(query_id)
        except Exception as e:
            logger.warning("Ошибка answer_callback_query: %s", e)

        if data.startswith("rev_more_"):
            try:
                offset = int(data.split("_")[2])
            except (IndexError, ValueError):
                offset = 0
            self.handle_reviews(chat_id, offset=offset)

        elif data.startswith("ord_more_"):
            try:
                offset = int(data.split("_")[2])
            except (IndexError, ValueError):
                offset = 0
            self.handle_orders(chat_id, offset=offset)

    def get_user_shops(self, chat_id):
        return list(
            CoffeeShop.objects.filter(
                Q(telegram_recipients__telegram_id=chat_id, telegram_recipients__is_active=True)
                | Q(telegram_id=chat_id)
            ).distinct()
        )

    def send_not_bound_message(self, chat_id):
        msg = (
            "⚠️ <b>Кофейня не привязана</b>\n\n"
            f"Ваш Telegram ID (<code>{chat_id}</code>) пока не привязан ни к одной точке.\n\n"
            "Для привязки откройте панель управления кофейней и нажмите "
            "кнопку «Подключить через Telegram» или укажите ваш ID в настройках точки."
        )
        try:
            telegram_bot.send_review_to_user(chat_id, msg, parse_mode="HTML")
        except Exception as e:
            logger.error("Ошибка отправки сообщения о непривязанном аккаунте: %s", e)

    def send_welcome_message(self, chat_id, first_name):
        shops = self.get_user_shops(chat_id)
        if shops:
            shop_names = ", ".join(s.street for s in shops if s.street) or f"{len(shops)} кофеен"
            msg = (
                f"👋 Здравствуйте, <b>{html.escape(first_name)}</b>!\n\n"
                f"Я официальный бот сети кофейных пространств Happy Island 🏝️\n\n"
                f"Вы подключены к кофейням: <b>{html.escape(shop_names)}</b>.\n"
                f"🆔 Ваш Telegram ID: <code>{chat_id}</code>\n\n"
                f"Выберите интересующий пункт меню ниже ⬇️"
            )
            try:
                telegram_bot.send_review_to_user(chat_id, msg, parse_mode="HTML", reply_markup=MAIN_KEYBOARD)
            except Exception as e:
                logger.error("Ошибка отправки приветствия: %s", e)
        else:
            msg = (
                f"👋 Привет, <b>{html.escape(first_name)}</b>!\n\n"
                f"Я официальный бот сети кофейных пространств Happy Island 🏝️\n\n"
                f"🆔 Ваш Telegram ID: <code>{chat_id}</code>\n\n"
                f"👉 Чтобы подключить получение отзывов и управление кофейней, откройте "
                f"панель управления кофейней и нажмите кнопку «Подключить через Telegram», "
                f"либо введите ваш ID в настройках точки."
            )
            try:
                telegram_bot.send_review_to_user(chat_id, msg, parse_mode="HTML")
            except Exception as e:
                logger.error("Ошибка отправки приветствия: %s", e)

    def send_help_message(self, chat_id):
        shops = self.get_user_shops(chat_id)
        msg = (
            "ℹ️ <b>Справка по боту Happy Island</b>\n\n"
            "Бот позволяет администраторам и управляющим контролировать работу кофеен в реальном времени:\n\n"
            "• 💬 <b>История отзывов</b> — последние отзывы гостей с оценками и комментариями\n"
            "• 📦 <b>История заказов</b> — последние заказы, состав и статусы оплаты\n"
            "• 📊 <b>Сводка за сегодня</b> — выручка, число чеков, средний чек и рейтинг за текущий день\n"
            "• ⏱ <b>Текущая смена</b> — статус открытой смены, бариста и текущая касса\n"
            "• 📍 <b>Мои кофейни</b> — адреса и параметры подключенных точек\n\n"
            f"🆔 Ваш Telegram ID: <code>{chat_id}</code>"
        )
        reply_markup = MAIN_KEYBOARD if shops else None
        try:
            telegram_bot.send_review_to_user(chat_id, msg, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as e:
            logger.error("Ошибка отправки справки: %s", e)

    def send_default_message(self, chat_id):
        shops = self.get_user_shops(chat_id)
        reply_markup = MAIN_KEYBOARD if shops else None
        msg = (
            "🤖 Я автоматический ассистент Happy Island.\n"
            f"🆔 Ваш Telegram ID: <code>{chat_id}</code>\n\n"
            "Воспользуйтесь кнопками меню ниже или напишите /start для начала работы."
        )
        try:
            telegram_bot.send_review_to_user(chat_id, msg, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as e:
            logger.error("Ошибка отправки сообщения по умолчанию: %s", e)

    def handle_bind(self, chat_id, username, first_name, token):
        from coffee_shop.models import CoffeeShopTelegramRecipient

        token = token.strip()
        cache_key = f"tg_bind_{token}"
        shop_id = cache.get(cache_key)
        logger.info("Попытка привязки Telegram: chat_id=%s, token=%s, shop_id=%s", chat_id, token, shop_id)

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

            recipient, _ = CoffeeShopTelegramRecipient.objects.update_or_create(
                coffee_shop=shop,
                telegram_id=chat_id,
                defaults={
                    "telegram_username": f"@{username}" if username else "",
                    "first_name": first_name or "",
                    "is_active": True,
                },
            )

            # Сохраняем как основной telegram_id, если он еще не был указан
            if not shop.telegram_id:
                shop.telegram_id = chat_id
                shop.telegram_username = recipient.telegram_username or first_name
                shop.save(update_fields=["telegram_id", "telegram_username"])

            cache.delete(cache_key)
            status_data = {
                "status": "linked",
                "shop_id": shop.id,
                "recipient_id": recipient.id,
                "telegram_id": chat_id,
                "telegram_username": recipient.telegram_username,
                "first_name": recipient.first_name,
            }
            cache.set(f"tg_bind_status_{token}", status_data, timeout=300)

            shop_desc = f"{shop.street}, {shop.building_number}" if shop.street else str(shop)
            city_name = getattr(shop.city, "name", "") if shop.city else ""
            full_addr = f"{city_name}, {shop_desc}".strip(", ")

            success_msg = (
                f"✅ <b>Вы успешно подключены к кофейне!</b>\n\n"
                f"📍 Точка: <b>{html.escape(full_addr)}</b>\n\n"
                f"Теперь вам доступны оперативные уведомления о заказах и отзывах, "
                f"а также меню аналитики и истории ниже ⬇️"
            )
            telegram_bot.send_review_to_user(chat_id, success_msg, parse_mode="HTML", reply_markup=MAIN_KEYBOARD)
            logger.info("Пользователь %s (@%s) успешно подключен к кофейне %s (ID %s)", chat_id, username, full_addr, shop_id)

        except CoffeeShop.DoesNotExist:
            telegram_bot.send_review_to_user(chat_id, "❌ Ошибка: привязываемая кофейня не найдена в базе данных.")
        except Exception as e:
            logger.exception("Ошибка при сохранении привязки кофейни: %s", e)
            telegram_bot.send_review_to_user(chat_id, "❌ Произошла ошибка при привязке. Попробуйте еще раз позже.")

    def handle_reviews(self, chat_id, offset=0, limit=5):
        shops = self.get_user_shops(chat_id)
        if not shops:
            self.send_not_bound_message(chat_id)
            return

        qs = ReviewsCoffeeShop.objects.filter(coffee_shop__in=shops).select_related(
            "coffee_shop", "user", "orders"
        ).order_by("-id")
        total_count = qs.count()

        if total_count == 0:
            telegram_bot.send_review_to_user(
                chat_id, "💬 <b>История отзывов</b>\n\nОтзывов пока нет.",
                parse_mode="HTML", reply_markup=MAIN_KEYBOARD
            )
            return

        reviews = list(qs[offset : offset + limit])
        if not reviews:
            telegram_bot.send_review_to_user(
                chat_id, "💬 Больше отзывов нет.",
                parse_mode="HTML", reply_markup=MAIN_KEYBOARD
            )
            return

        page_num = (offset // limit) + 1
        total_pages = (total_count + limit - 1) // limit
        lines = [f"💬 <b>История отзывов</b> (стр. {page_num} из {total_pages}, всего: {total_count})\n"]

        for r in reviews:
            stars = "⭐" * r.evaluation + "☆" * (5 - r.evaluation)
            user_name = html.escape(r.user.first_name) if (r.user and r.user.first_name) else "Гость"

            date_str = ""
            if hasattr(r, "orders") and r.orders:
                dt = r.orders.created_at or r.orders.updated_at
                if dt:
                    date_str = timezone.localtime(dt).strftime("%d.%m.%Y %H:%M")

            tags = []
            if r.very_tasty:
                tags.append("#вкусно")
            if r.wide_range:
                tags.append("#ассортимент")
            if r.nice_prices:
                tags.append("#хорошие_цены")
            tags_str = (" " + " ".join(tags)) if tags else ""

            shop_tag = f"📍 <i>{html.escape(r.coffee_shop.street)}</i>\n" if (len(shops) > 1 and r.coffee_shop) else ""
            comment_str = f"\n📝 <i>«{html.escape(r.comments)}»</i>" if r.comments else ""
            order_part = f" • Заказ #{r.orders_id}" if r.orders_id else ""
            date_part = f" • {date_str}" if date_str else ""

            review_card = (
                f"{shop_tag}"
                f"{stars} <b>{user_name}</b>{order_part}{date_part}{tags_str}"
                f"{comment_str}\n"
                f"──────────────────"
            )
            lines.append(review_card)

        reply_markup = None
        if offset + limit < total_count:
            rem = total_count - (offset + limit)
            next_n = min(limit, rem)
            reply_markup = {
                "inline_keyboard": [
                    [{"text": f"➡️ Показать ещё ({next_n})", "callback_data": f"rev_more_{offset + limit}"}]
                ]
            }

        msg_text = "\n".join(lines)
        try:
            telegram_bot.send_review_to_user(chat_id, msg_text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as e:
            logger.error("Ошибка отправки отзывов: %s", e)

    def handle_orders(self, chat_id, offset=0, limit=5):
        shops = self.get_user_shops(chat_id)
        if not shops:
            self.send_not_bound_message(chat_id)
            return

        qs = Orders.objects.filter(coffee_shop__in=shops).select_related(
            "coffee_shop", "user", "cart"
        ).prefetch_related("cart__items__product").order_by("-id")
        total_count = qs.count()

        if total_count == 0:
            telegram_bot.send_review_to_user(
                chat_id, "📦 <b>История заказов</b>\n\nЗаказов пока нет.",
                parse_mode="HTML", reply_markup=MAIN_KEYBOARD
            )
            return

        orders = list(qs[offset : offset + limit])
        if not orders:
            telegram_bot.send_review_to_user(
                chat_id, "📦 Больше заказов нет.",
                parse_mode="HTML", reply_markup=MAIN_KEYBOARD
            )
            return

        status_labels = {
            Orders.COMPLETED: "🟢 Выполнен",
            Orders.IN_PROGRESS: "🟡 Готовится",
            Orders.WAITING: "⏳ Ожидает",
            Orders.CANCELED: "🔴 Отменен",
            Orders.NEW: "🆕 Новый",
        }
        pay_labels = {
            Orders.PAID: "💳 Оплачено",
            Orders.PENDING: "⏳ Ожидает оплаты",
            Orders.FAILED: "❌ Ошибка оплаты",
            Orders.NEW: "🆕 Новый",
        }

        page_num = (offset // limit) + 1
        total_pages = (total_count + limit - 1) // limit
        lines = [f"📦 <b>История заказов</b> (стр. {page_num} из {total_pages}, всего: {total_count})\n"]

        for o in orders:
            st_str = status_labels.get(o.status_orders, f"⚪ {o.status_orders}")
            pay_str = pay_labels.get(o.payment_status, o.payment_status)
            dt = o.created_at or o.updated_at
            date_str = timezone.localtime(dt).strftime("%d.%m.%Y %H:%M") if dt else "—"
            guest = html.escape(o.user.first_name) if (o.user and o.user.first_name) else "Гость"

            item_names = []
            if o.cart_id and hasattr(o, "cart"):
                for item in o.cart.items.all():
                    p_name = html.escape(item.product.product) if item.product else "Позиция"
                    size = f" ({item.size})" if item.size else ""
                    item_names.append(f"{p_name}{size} x{item.amount}")
            items_str = ", ".join(item_names) if item_names else "Состав не указан"

            comment_str = f"\n💬 <i>«{html.escape(o.client_comments)}»</i>" if o.client_comments else ""
            shop_tag = f"📍 <i>{html.escape(o.coffee_shop.street)}</i>\n" if (len(shops) > 1 and o.coffee_shop) else ""

            order_card = (
                f"{shop_tag}"
                f"<b>Заказ #{o.id}</b> • {st_str}\n"
                f"👤 {guest} • 📅 {date_str}\n"
                f"☕ {items_str}\n"
                f"💵 <b>{o.full_price:,.2f} ₽</b> ({pay_str}){comment_str}\n"
                f"──────────────────"
            )
            lines.append(order_card)

        reply_markup = None
        if offset + limit < total_count:
            rem = total_count - (offset + limit)
            next_n = min(limit, rem)
            reply_markup = {
                "inline_keyboard": [
                    [{"text": f"➡️ Показать ещё ({next_n})", "callback_data": f"ord_more_{offset + limit}"}]
                ]
            }

        msg_text = "\n".join(lines)
        try:
            telegram_bot.send_review_to_user(chat_id, msg_text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as e:
            logger.error("Ошибка отправки заказов: %s", e)

    def handle_today_summary(self, chat_id):
        shops = self.get_user_shops(chat_id)
        if not shops:
            self.send_not_bound_message(chat_id)
            return

        today = timezone.localdate()
        today_orders = Orders.objects.filter(coffee_shop__in=shops).filter(
            Q(created_at__date=today) | Q(created_at__isnull=True, updated_at__date=today)
        )

        total_orders_count = today_orders.count()
        completed_orders = today_orders.filter(status_orders=Orders.COMPLETED)
        completed_count = completed_orders.count()
        canceled_count = today_orders.filter(status_orders=Orders.CANCELED).count()
        active_count = today_orders.filter(status_orders__in=[Orders.IN_PROGRESS, Orders.WAITING, Orders.NEW]).count()

        revenue = completed_orders.aggregate(
            total=Coalesce(Sum("full_price"), Decimal("0.00"))
        )["total"]

        avg_check = (revenue / completed_count) if completed_count > 0 else Decimal("0.00")

        today_reviews = ReviewsCoffeeShop.objects.filter(coffee_shop__in=shops).filter(
            Q(orders__created_at__date=today) | Q(orders__isnull=True)
        )
        reviews_count = today_reviews.count()
        avg_rating = today_reviews.aggregate(avg=Avg("evaluation"))["avg"]
        avg_rating_str = f"⭐ {avg_rating:.1f} / 5.0" if avg_rating else "Нет оценок"

        shop_header = f"📍 {html.escape(shops[0].street)}" if len(shops) == 1 else f"📍 Сеть: {len(shops)} кофеен"

        msg = (
            f"📊 <b>Сводка за сегодня ({today.strftime('%d.%m.%Y')})</b>\n"
            f"{shop_header}\n\n"
            f"💰 <b>Выручка:</b> {revenue:,.2f} ₽\n"
            f"🧾 <b>Закрыто чеков:</b> {completed_count}\n"
            f"📈 <b>Средний чек:</b> {avg_check:,.2f} ₽\n\n"
            f"📦 <b>Всего заказов:</b> {total_orders_count}\n"
            f"  • В работе / ожидают: {active_count}\n"
            f"  • Отменено: {canceled_count}\n\n"
            f"💬 <b>Отзывов за сегодня:</b> {reviews_count}\n"
            f"✨ <b>Средний рейтинг:</b> {avg_rating_str}"
        )
        try:
            telegram_bot.send_review_to_user(chat_id, msg, parse_mode="HTML", reply_markup=MAIN_KEYBOARD)
        except Exception as e:
            logger.error("Ошибка отправки сводки за сегодня: %s", e)

    def handle_current_shift(self, chat_id):
        shops = self.get_user_shops(chat_id)
        if not shops:
            self.send_not_bound_message(chat_id)
            return

        active_shifts = Shift.objects.filter(
            staff__place_of_work__in=shops,
            status_shift="Open",
        ).select_related("staff__users", "staff__place_of_work")

        if not active_shifts.exists():
            msg = "⏱ <b>Текущая смена</b>\n\nВ ваших кофейнях сейчас нет открытых смен."
            try:
                telegram_bot.send_review_to_user(chat_id, msg, parse_mode="HTML", reply_markup=MAIN_KEYBOARD)
            except Exception as e:
                logger.error("Ошибка отправки статуса смены: %s", e)
            return

        blocks = ["⏱ <b>Информация о текущих сменах:</b>\n"]
        for s in active_shifts:
            try:
                s.update_shift_statistics(save=True)
            except Exception:
                pass

            barista = s.staff.users if s.staff else None
            if barista:
                full_name = f"{barista.first_name} {barista.last_name or ''}".strip()
                barista_name = full_name if full_name else (barista.first_name or barista.login)
            else:
                barista_name = "Сотрудник"
            shop_name = f"{s.staff.place_of_work.street}, {s.staff.place_of_work.building_number}".strip(", ") if (s.staff and s.staff.place_of_work) else "Точка"
            start_str = timezone.localtime(s.start_time).strftime("%H:%M (%d.%m)") if s.start_time else "не зафиксировано"

            blocks.append(
                f"📍 <b>{html.escape(shop_name)}</b>\n"
                f"👤 Бариста: <b>{html.escape(barista_name)}</b>\n"
                f"⏰ Начало: {start_str}\n"
                f"🧾 Заказов за смену: {s.number_orders_closed}\n"
                f"💰 Сумма смены: {s.amount_closed_orders:,.2f} ₽\n"
                f"──────────────────"
            )

        msg = "\n".join(blocks)
        try:
            telegram_bot.send_review_to_user(chat_id, msg, parse_mode="HTML", reply_markup=MAIN_KEYBOARD)
        except Exception as e:
            logger.error("Ошибка отправки информации о смене: %s", e)

    def handle_my_shops(self, chat_id):
        shops = self.get_user_shops(chat_id)
        if not shops:
            self.send_not_bound_message(chat_id)
            return

        blocks = ["📍 <b>Ваши подключенные кофейни:</b>\n"]
        for s in shops:
            city_name = s.city.name if s.city else ""
            addr = f"{city_name}, {s.street}, {s.building_number}".strip(", ")
            hours = f"{s.time_open.strftime('%H:%M')} – {s.time_close.strftime('%H:%M')}"
            email = s.email or "не указан"
            crm = s.crm_system.name if s.crm_system else "не подключена"
            acq = s.acquiring.name if s.acquiring else "не подключен"

            blocks.append(
                f"🏠 <b>{html.escape(addr)}</b>\n"
                f"⏰ Режим работы: {hours}\n"
                f"✉️ Email для отзывов: {html.escape(email)}\n"
                f"🖥 CRM: {html.escape(crm)}\n"
                f"💳 Эквайринг: {html.escape(acq)}\n"
                f"🆔 Telegram ID: <code>{s.telegram_id}</code>\n"
                f"──────────────────"
            )

        msg = "\n".join(blocks)
        try:
            telegram_bot.send_review_to_user(chat_id, msg, parse_mode="HTML", reply_markup=MAIN_KEYBOARD)
        except Exception as e:
            logger.error("Ошибка отправки списка кофеен: %s", e)
