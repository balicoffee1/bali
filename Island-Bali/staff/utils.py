import base64
import binascii

from django.core.files.base import ContentFile

from orders.models import Orders
from staff.models import Shift, Staff


def decode_receipt_photo(order_id, photo):
    """Decode a receipt sent either as a data URI or as plain base64.

    Older mobile builds send plain base64 under ``photo_base64`` while the
    original API expected a data URI under ``photo``.  Supporting both formats
    keeps already installed clients working during a rolling deployment.
    """
    if not isinstance(photo, str) or not photo.strip():
        raise ValueError("Receipt photo is required")

    encoded = photo.strip()
    extension = "jpg"
    if ";base64," in encoded:
        header, encoded = encoded.split(";base64,", 1)
        mime_type = header.removeprefix("data:").lower()
        extension = {
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/heic": "heic",
            "image/heif": "heif",
        }.get(mime_type, "jpg")

    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Receipt photo is not valid base64") from exc
    if not content:
        raise ValueError("Receipt photo is empty")

    return ContentFile(content, name=f"order_{order_id}_receipt.{extension}")


def is_staff_for_order(user, order) -> bool:
    """
    M0 п.3.2: единая проверка IDOR для staff-эндпоинтов orders/staff —
    сотрудник должен реально числиться в staff.models.Staff за тем же
    coffee_shop, что и заказ. Раньше staff-эндпоинты принимали любой
    order_id от любого аутентифицированного пользователя без этой проверки.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if order.coffee_shop_id is None:
        return False
    return Staff.objects.filter(users=user, place_of_work_id=order.coffee_shop_id).exists()


def get_order_if_pending(order_id):
    """Эта функция будет отвечать за получение заказа и проверку его
    текущего статуса.
    """
    try:
        order = Orders.objects.get(id=order_id)
        if order.status_orders != "Waiting":
            return None, "Заказ не находится в состоянии «Ожидание»."
        return order, None
    except Orders.DoesNotExist:
        return None, "Order not found"


def get_order_if_new(order_id):
    """Эта функция будет отвечать за получение заказа и проверку его
    новизны.
    """
    try:
        order = Orders.objects.get(id=order_id)
        return order, None
    except Orders.DoesNotExist:
        return None, "Order not found"


def update_order_time_to_finish(order, new_time_to_finish):
    """Функция для обновления времени завершения заказа"""
    if new_time_to_finish:
        order.time_is_finish = new_time_to_finish
        order.save()


def update_order_comments(order, new_comments):
    """Функция для обновления комментариев к заказу.

    M7: через сервис, а не голым save() — staff_comments входит в payload,
    который уходит клиенту, значит изменение обязано публиковать событие.
    """
    if new_comments:
        from orders.services import OrderStateService

        OrderStateService.update_presentation(
            order.id, actor_type="staff", staff_comments=new_comments
        )
        order.refresh_from_db()


def get_completed_orders(sorting_datevalue):
    """Получение списка заказов в статусе "Completed"."""
    orders = Orders.objects.filter(
        status_orders=Orders.COMPLETED,
        time_is_finish__date=sorting_datevalue
    ).order_by("-created_at", "time_is_finish")
    return orders


def is_valid_order_status(status):
    """Проверяет, является ли статус заказа валидным."""
    valid_statuses = [order_status[0] for order_status in Orders.StatusOrders]
    return status in valid_statuses


def filter_orders_by_status(status):
    """Фильтрация заказов по указанному статусу."""
    return Orders.objects.filter(status_orders=status)


def open_shift(start_time, staff):
    """Создание и открытие новой смены с заданным временем начала."""
    shift = Shift.objects.create(start_time=start_time, status_shift="Open", staff=staff)
    return shift


def close_shift(start_time, end_time, staff):
    """
    Закрытие смены, соответствующей заданному времени начала.
    Возвращает смену, если она найдена и закрыта, иначе возвращает None и
     сообщение об ошибке.
    """
    try:

        shift = Shift.objects.get(start_time=start_time, staff=staff)
        shift.update_shift_statistics()
        shift.status_shift = "Closed"
        shift.end_time = end_time
        shift.save()
        return shift, None
    except Shift.DoesNotExist:
        return None, "Shift not found"


# update_order_status / cancel_order_with_comment / change_order_status_to_completed /
# update_payment_status удалены отсюда (M1 п.18): все они напрямую писали
# order.status_orders / order.payment_status + order.save() в обход какой-либо
# state machine (в т.ч. update_order_status безусловно форсировал "Waiting" даже
# для Completed/Canceled заказа, а cancel_order_with_comment — "Canceled" даже
# поверх уже терминального статуса). Эквивалентная логика теперь — вызовы
# OrderStateService.accept/cancel/complete напрямую из staff/views.py, которые
# проверяют допустимость перехода и делают это атомарно под select_for_update.
