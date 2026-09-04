import json
import random
import re

import phonenumbers
import requests
from django.core.mail import send_mail
from loguru import logger
from requests.auth import HTTPBasicAuth

from island_bali.settings import (
    EMAIL_HOST_USER,
    SMS_API_URL,
    SMS_ENABLED,
    SMS_LOGIN,
    SMS_PASSWORD,
    SMS_SENDER,
    SMS_TIMEOUT,
)


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


class SmsSendError(Exception):
    """Не удалось отправить SMS через провайдера."""


def normalize_phone(phone: str) -> str:
    """Приводит номер к формату 7XXXXXXXXXX, который ждёт iqsms."""
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


def send_sms(phone: str, text: str) -> dict:
    """
    Отправляет SMS через iqsms.ru (Rocket SMS).

    Возвращает разобранный ответ провайдера, при неуспехе бросает SmsSendError.
    Если отправка выключена (SMS_ENABLED=False) или не заданы учётные данные —
    сообщение только пишется в лог.
    """
    recipient = normalize_phone(phone)
    if not recipient:
        raise SmsSendError("Не указан номер телефона")

    if not (SMS_ENABLED and SMS_LOGIN and SMS_PASSWORD):
        logger.warning(
            "SMS отправка отключена, сообщение не доставлено. "
            "Телефон: {}, текст: {}", recipient, text
        )
        return {"status": "disabled"}

    body = {
        "messages": [
            {
                "phone": recipient,
                "sender": SMS_SENDER,
                "clientId": recipient,
                "text": text,
            }
        ],
        "login": SMS_LOGIN,
        "password": SMS_PASSWORD,
    }

    try:
        response = requests.post(
            SMS_API_URL,
            data=json.dumps(body),
            headers={"Content-Type": "application/json"},
            timeout=SMS_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.exceptions.RequestException, ValueError) as ex:
        logger.error("Ошибка обращения к SMS-шлюзу: {}", ex)
        raise SmsSendError(
            "Сервер отправки СМС в данный момент не работает. "
            "Попробуйте позже"
        ) from ex

    messages = payload.get("messages") or []
    status_ = messages[0].get("status") if messages else payload.get("status")
    if status_ not in ("accepted", "queued"):
        logger.error("SMS-шлюз отклонил сообщение: {}", payload)
        raise SmsSendError(
            "Сервер отправки СМС в данный момент не работает. "
            "Попробуйте позже"
        )

    logger.info("SMS отправлено на {}, статус {}", recipient, status_)
    return payload


def send_phone_reset(phone, code=None):
    """Отправляет код подтверждения на телефон. Возвращает отправленный код."""
    if code is None:
        code = str(random.randint(1000, 9999))

    send_sms(
        phone,
        f"Ваш код подтверждения приложения Islandbali: {code}. "
        f"Не говорите код!",
    )
    return code


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
