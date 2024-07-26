from telethon import TelegramClient

api_id = 16223511
api_hash = "66c83b36a77573871b55b72c6c57018f"


async def send_message_from_personal_account(api_id, api_hash, recipients,
                                             message):
    """
    Отправляет сообщение от вашего личного аккаунта в Telegram.

    :param api_id: Ваш API ID, полученный от Telegram.
    :param api_hash: Ваш API Hash, полученный от Telegram.
    :param recipients: Список username или ID получателей в Telegram.
    :param message: Текст сообщения для отправки.
    """
    async with (TelegramClient('session_name', api_id, api_hash)
                as client):
        for recipient in recipients:
            await client.send_message(recipient, message)

# Пример использования
# asyncio.run(send_message_from_personal_account(api_id, api_hash,
# ["@KrasikovaYana", "@col1ecti0n"], "Отзыв"))
