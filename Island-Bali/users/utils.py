import json
import random
import re

import phonenumbers
import requests
from django.core.mail import send_mail
from requests.auth import HTTPBasicAuth

from island_bali.settings import EMAIL_HOST_USER

# Клиент провайдера переехал в users/sms.py. Реэкспорт — потому что
# вызывающие обращаются к нему как utils.send_sms / utils.SmsSendError.
from .sms import SmsSendError, send_sms  # noqa: F401


def is_email(string: str):
    return re.fullmatch(r"[^@]+@[^@]+\.[^@]+", string)


def ru_phone(phone: str):
    try:
        return phone[-10:]
    except IndexError:
        return phone


def is_phone_number(string: str):
    try:
        parsed_number = phonenumbers.parse(string, None)
        return phonenumbers.is_possible_number(parsed_number)
    except Exception:
        return False


def normalize_phone(phone: str) -> str:
    """Номер в виде ``7XXXXXXXXXX`` — так он сравнивается и хранится.

    Провайдеру нужен тот же номер с ведущим плюсом; за это отвечает
    ``users.sms.format_phone``.
    """
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


def send_phone_reset(phone, code=None):
    """Отправляет код подтверждения на телефон.

    Возвращает пару ``(код, SentMessage)``: ``smscId`` из второго элемента
    сохраняется в ``PhoneVerification``, чтобы позже спросить у провайдера,
    дошло ли сообщение.
    """
    if code is None:
        code = generate_code()

    sent = send_sms(
        phone,
        f"Ваш код подтверждения приложения Islandbali: {code}. "
        f"Не говорите код!",
    )
    return code, sent


def send_mail_reset(email):
    code = random.SystemRandom().randint(100000, 999999)
    try:
        send_mail(
            "Your code",
            f"Введите этот код для подтверждения личности на "
            f"сервисе Test:" f" {code}",
            EMAIL_HOST_USER,
            [email],
            fail_silently=False,
        )
        return code
    except Exception as ex:
        return ex


def search_clients(phone, login, password):
    """ Производит поиск клиента в QuickRestoAPI """
    data = {'search': phone}
    headers = {'Content-Type': 'application/json'}
    auth = HTTPBasicAuth(login, password)
    data_json = json.dumps(data)

    try:
        with requests.post(
                'https://vp336.quickresto.ru/platform/online/bonuses/'
                'filterCustomers',
                data=data_json, headers=headers, auth=auth) as response:
            response.raise_for_status()

            dict_ = response.json()
            customers = dict_.get('customers', [])
            discount_values = (
                customer.get('customerGroup', {}).get('discountValue') for
                customer
                in customers)
            return next(
                (value for value in discount_values if value is not None),
                None)

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


def generate_code() -> str:
    """Криптостойкий 4-значный код подтверждения."""
    return f"{random.SystemRandom().randint(0, 9999):04d}"


def is_test_phone(phone) -> bool:
    """Тестовый номер для ревью в сторах: SMS не шлём, код фиксированный."""
    from django.conf import settings

    if not settings.SMS_TEST_LOGIN_ENABLED:
        return False
    return normalize_phone(phone) == normalize_phone(settings.SMS_TEST_PHONE)


def verify_phone_code(phone: str, code) -> tuple:
    """
    Проверяет код подтверждения телефона. Возвращает (успех, текст ошибки).

    Код обязателен всегда: вход без подтверждения не предусмотрен.
    """
    from django.conf import settings

    from .models import PhoneVerification

    if code in (None, ""):
        return False, "Требуется код подтверждения из SMS."

    code = str(code).strip()

    if is_test_phone(phone):
        if code == settings.SMS_TEST_CODE:
            logger.info("Вход по тестовому номеру {}", phone)
            return True, ""
        return False, "Неверный код."

    return PhoneVerification.verify(phone, code)
