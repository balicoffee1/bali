"""Клиент JSON API СМС Дисконт (iqsms.ru).

Документация: https://iqsms.ru/api/api_json/

Один базовый URL и четыре метода поверх него:

===================  =========================================================
``send.json``        отправка, до 200 сообщений за запрос
``status.json``      статус доставки по ``smscId``, до 200 за запрос
``balance.json``     остаток на счёте
``senders.json``     утверждённые подписи отправителя
===================  =========================================================

Авторизация — ``login`` и ``password`` в теле каждого запроса.

Что было не так в прежней реализации (``users.utils.send_sms``):

* номер уходил как ``79991234567``, а документация требует ``+79991234567``;
* в ``clientId`` подставлялся номер телефона — по нему невозможно сверить
  статус, и два сообщения на один номер в одной пачке сливались;
* успехом считался статус ``queued``, которого ``send.json`` не возвращает
  вовсе: это статус доставки из ``status.json``;
* верхний ``status`` ответа (``ok`` / ``error``) не разбирался отдельно, и
  текст ошибки провайдера не попадал даже в лог;
* статус доставки и баланс не запрашивались никогда.
"""

import json
import uuid
from dataclasses import dataclass

import requests
from django.conf import settings
from loguru import logger

# Ограничения из документации.
MAX_MESSAGES_PER_REQUEST = 200

# Единственный статус, которым send.json подтверждает приём сообщения.
STATUS_ACCEPTED = "accepted"

# Статусы доставки status.json. Терминальные — те, после которых опрашивать
# сообщение больше незачем.
DELIVERY_QUEUED = "queued"
DELIVERY_SMSC_SUBMIT = "smsc submit"
DELIVERY_DELIVERED = "delivered"
DELIVERY_SMSC_REJECT = "smsc reject"
DELIVERY_ERROR = "delivery error"

DELIVERY_FINAL_STATUSES = frozenset(
    {DELIVERY_DELIVERED, DELIVERY_SMSC_REJECT, DELIVERY_ERROR}
)

# Осторожно: на неизвестный smscId провайдер отвечает не ошибкой, а `queued`
# (проверено на живом API). То есть «queued» означает либо «правда в очереди»,
# либо «такого сообщения у нас нет» — отличить нельзя. Поэтому опрос статуса
# ограничен по возрасту записи (SMS_STATUS_MAX_AGE_HOURS), а не крутится
# бесконечно в ожидании финального статуса.

# Ответ, который видит пользователь приложения. Контракт зафиксирован в
# docs/sms-auth-contract.md: 503 с этим текстом.
GATEWAY_DOWN_MESSAGE = (
    "Сервер отправки СМС в данный момент не работает. Попробуйте позже"
)

# Расшифровка отказов провайдера — только для логов, наружу не уходит.
SEND_ERROR_HINTS = {
    "sender address invalid": (
        "подпись отправителя не зарегистрирована у провайдера; "
        "список доступных: manage.py sms_senders"
    ),
    "invalid mobile phone": "номер не принят провайдером",
    "text is empty": "пустой текст сообщения",
    "not enough credits": (
        "на счёте закончились деньги; проверить: manage.py sms_balance"
    ),
}


class SmsSendError(Exception):
    """Не удалось отправить SMS через провайдера."""


@dataclass(frozen=True)
class SentMessage:
    """Результат приёма сообщения провайдером."""

    smsc_id: str
    client_id: str
    status: str

    @property
    def accepted(self) -> bool:
        return self.status == STATUS_ACCEPTED


def format_phone(phone) -> str:
    """Номер в формате документации: ``+71234567890``.

    ``users.utils.normalize_phone`` приводит номер к ``7XXXXXXXXXX`` — этот
    вид используется для сравнения и хранения. Провайдеру нужен тот же номер,
    но с ведущим плюсом.
    """
    from .utils import normalize_phone

    digits = normalize_phone(phone)
    return f"+{digits}" if digits else ""


def new_client_id() -> str:
    """Свой идентификатор сообщения, по которому потом сверяется статус.

    Раньше сюда подставлялся номер телефона: два кода на один номер получали
    одинаковый clientId, и сопоставить ответ провайдера с записью было нельзя.
    """
    return uuid.uuid4().hex[:16]


def _base_url() -> str:
    url = settings.SMS_API_BASE_URL.strip()
    return url if url.endswith("/") else url + "/"


def _credentials() -> dict:
    return {"login": settings.SMS_LOGIN, "password": settings.SMS_PASSWORD}


def is_configured() -> bool:
    return bool(
        settings.SMS_ENABLED and settings.SMS_LOGIN and settings.SMS_PASSWORD
    )


def _post(endpoint: str, payload: dict) -> dict:
    """POST на ``endpoint`` с учётными данными. Возвращает разобранный ответ.

    Бросает :class:`SmsSendError` и на сетевую ошибку, и на ``status: error``
    в теле: для вызывающего это один и тот же случай «шлюз не сработал».
    """
    body = {**_credentials(), **payload}

    try:
        response = requests.post(
            _base_url() + endpoint,
            data=json.dumps(body),
            headers={"Content-Type": "application/json"},
            timeout=settings.SMS_TIMEOUT,
        )
        response.raise_for_status()
        parsed = response.json()
    except (requests.exceptions.RequestException, ValueError) as ex:
        logger.error("SMS-шлюз {} недоступен: {}", endpoint, ex)
        raise SmsSendError(GATEWAY_DOWN_MESSAGE) from ex

    # Верхний status относится ко всему запросу: при error в теле нет ни
    # messages, ни balance — только описание отказа.
    if parsed.get("status") != "ok":
        description = parsed.get("description") or parsed.get("status")
        logger.error("SMS-шлюз {} отклонил запрос: {}", endpoint, parsed)
        raise SmsSendError(
            GATEWAY_DOWN_MESSAGE
            if not description
            else f"{GATEWAY_DOWN_MESSAGE} ({description})"
        )

    return parsed


def send_sms(phone: str, text: str, client_id: str = None) -> SentMessage:
    """Отправляет одно сообщение. Возвращает приём провайдером.

    Если отправка выключена (``SMS_ENABLED=False``) или не заданы учётные
    данные, сообщение только пишется в лог, а результат помечается статусом
    ``disabled`` — чтобы вызывающий не принял это за реальную отправку.
    """
    recipient = format_phone(phone)
    if not recipient:
        raise SmsSendError("Не указан номер телефона")

    client_id = client_id or new_client_id()

    if not is_configured():
        logger.warning(
            "SMS отправка отключена, сообщение не доставлено. "
            "Телефон: {}, текст: {}", recipient, text
        )
        return SentMessage(smsc_id="", client_id=client_id, status="disabled")

    message = {
        "phone": recipient,
        "text": text,
        "clientId": client_id,
    }
    # Подпись обязана быть в списке senders.json, иначе провайдер вернёт
    # sender address invalid. Пустое значение — отправка под номером.
    if settings.SMS_SENDER:
        message["sender"] = settings.SMS_SENDER

    parsed = _post("send.json", {"messages": [message]})

    messages = parsed.get("messages") or []
    if not messages:
        logger.error("SMS-шлюз вернул пустой список сообщений: {}", parsed)
        raise SmsSendError(GATEWAY_DOWN_MESSAGE)

    result = messages[0]
    status_ = result.get("status")

    if status_ != STATUS_ACCEPTED:
        hint = SEND_ERROR_HINTS.get(status_, "неизвестный отказ провайдера")
        logger.error(
            "SMS на {} не принято: статус {} ({}). Ответ: {}",
            recipient, status_, hint, parsed
        )
        raise SmsSendError(GATEWAY_DOWN_MESSAGE)

    sent = SentMessage(
        smsc_id=str(result.get("smscId") or ""),
        client_id=str(result.get("clientId") or client_id),
        status=status_,
    )
    logger.info(
        "SMS принято провайдером: {} -> smscId {}", recipient, sent.smsc_id
    )
    return sent


def check_status(smsc_ids) -> dict:
    """Статусы доставки по списку ``smscId``. Возвращает {smscId: статус}.

    Провайдер принимает не больше 200 идентификаторов за запрос, поэтому
    список режется на пачки.
    """
    ids = [str(smsc_id) for smsc_id in smsc_ids if smsc_id]
    if not ids or not is_configured():
        return {}

    statuses = {}
    for start in range(0, len(ids), MAX_MESSAGES_PER_REQUEST):
        chunk = ids[start:start + MAX_MESSAGES_PER_REQUEST]
        parsed = _post(
            "status.json",
            {"messages": [{"smscId": smsc_id} for smsc_id in chunk]},
        )
        for message in parsed.get("messages") or []:
            smsc_id = str(message.get("smscId") or "")
            if smsc_id:
                statuses[smsc_id] = message.get("status")

    return statuses


def get_balance() -> list:
    """Остатки на счёте: список словарей ``{type, balance, credit}``."""
    return _post("balance.json", {}).get("balance") or []


def rub_balance():
    """Рублёвый остаток или None, если провайдер его не вернул."""
    for entry in get_balance():
        if str(entry.get("type", "")).upper() == "RUB":
            try:
                return float(entry.get("balance"))
            except (TypeError, ValueError):
                return None
    return None


def get_senders() -> list:
    """Подписи отправителя: список словарей ``{name, status, info}``."""
    return _post("senders.json", {}).get("senders") or []


def active_sender_names() -> list:
    return [
        sender.get("name")
        for sender in get_senders()
        if sender.get("status") == "active" and sender.get("name")
    ]
