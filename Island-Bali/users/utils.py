import json
import random
import re

import phonenumbers
import requests
from django.core.mail import send_mail
from requests.auth import HTTPBasicAuth

from island_bali.settings import EMAIL_HOST_USER, SMS_LOGIN, SMS_PASSWORD


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


def send_phone_reset(phone, code):
    body = json.dumps(
        {
            "messages": [
                {
                    "phone": phone,
                    "sender": "Islandbali",
                    "clientId": f"{phone}",
                    "text": "Ваш код подтверждения приложения Islandbali: "
                            + str(code)
                            + ". Не говорите код!",
                }
            ],
            "statusQueueName": "myQueue",
            "showBillingDetails": True,
            "login": SMS_LOGIN,
            "password": SMS_PASSWORD,
        }
    )
    requests.post("https://api.iqsms.ru/messages/v2/send.json", data=body)
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
