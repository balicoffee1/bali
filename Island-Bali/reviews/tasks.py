import asyncio

from celery import shared_task
from django.core.mail import send_mail

from island_bali.settings import EMAIL_HOST_USER
from reviews.tg_bot import send_message_from_personal_account


@shared_task()
def send_review_for_email(review, email_coffeeshop, telegram_username):
    api_id = 16223511
    api_hash = "66c83b36a77573871b55b72c6c57018f"
    subject = "Оставлен плохой отзыв"
    message = generate_review_message(review)
    from_email = EMAIL_HOST_USER
    recipient_list_email = generate_recipient_list_email(email_coffeeshop)
    recepient_list_telegram = (generate_recipient_list_telegram
                               (telegram_username))

    send_mail(subject, message, from_email, recipient_list_email)
    asyncio.run(
        send_message_from_personal_account(
            api_id, api_hash, recepient_list_telegram, message
        )
    )
    return "Сообщения доставлены"


def generate_review_message(review):
    """Генерирует сообщение которое будет отправляться на почты"""
    very_tasty_str = "выбрал" if review["very_tasty"] else "не выбрал"
    wide_range_str = "выбрал" if review["wide_range"] else "не выбрал"
    nice_prices_str = "выбрал" if review["nice_prices"] else "не выбрал"

    message = (
        f"Отзыв был такой:\n"
        f"ID: {review['id']}\n"
        f"Оценка: {review['evaluation']}\n"
        f"Очень вкусно: {very_tasty_str}\n"
        f"Широкий ассортимент: {wide_range_str}\n"
        f"Приятные цены: {nice_prices_str}\n"
        f"Комментарий: {review['comments']}\n"
        f"ID кофейни: {review['coffee_shop']}\n"
        f"Пользователь: {review['user']}\n"
        f"ID заказа: {review['orders']}"
    )
    return message


def generate_recipient_list_email(email_coffeeshop):
    """Генерирует список почт"""
    default_recipients = ["makhotin.07@gmail.com"]
    return default_recipients + [email_coffeeshop]


def generate_recipient_list_telegram(telegram_username):
    default_recipients = ["@col1ecti0n"]
    list_tg = default_recipients + [telegram_username]
    print(list_tg)
    return list_tg
