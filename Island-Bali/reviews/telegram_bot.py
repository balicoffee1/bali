import telegram
from django.conf import settings

# Инициализируем бота с вашим токеном
bot = telegram.Bot(token=settings.TELEGRAM_BOT_TOKEN)

def send_review_to_user(chat_id, review_text):
    """
    Отправляет отзыв пользователю в Telegram.
    
    :param chat_id: ID чата пользователя в Telegram.
    :param review_text: Текст отзыва.
    """
    bot.send_message(chat_id=chat_id, text=review_text)
