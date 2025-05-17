import base64

from django.core.files.base import ContentFile

from orders.models import Orders
from staff.models import Shift


def change_receipt_photo(order, photo):
    if photo:
        format, imgstr = photo.split(";base64,")
        ext = format.split("/")[-1]
        data = ContentFile(
            base64.b64decode(imgstr), name=f"order_{order.id}_receipt.{ext}"
        )
        order.receipt_photo = data
    else:
        order.receipt_photo = None
    order.save()


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


def update_order_status(order):
    """Эта функция обновит статус и платежный статус заказа."""
    order.status_orders = "In Progress"
    order.payment_status = "Pending"
    order.save()
    return order


def update_order_time_to_finish(order, new_time_to_finish):
    """Функция для обновления времени завершения заказа"""
    if new_time_to_finish:
        order.time_is_finish = new_time_to_finish
        order.save()


def update_order_comments(order, new_comments):
    """Функция для обновления комментариев к заказу"""
    if new_comments:
        order.staff_comments = new_comments
        order.save()


def update_payment_status(order, payment_status):
    """Функция для обновления статуса платежа"""
    if payment_status == "Failed":
        order.payment_status = "Failed"
        order.save()


def cancel_order_with_comment(order, staff_comments):
    """Функция для удаления заказа с комментарием"""
    order.staff_comments = staff_comments
    order.status_orders = "Canceled"
    order.save()
    return order


def get_completed_orders():
    """Получение списка заказов в статусе "Completed"."""
    orders = Orders.objects.filter(status_orders="Completed").order_by("-created_at")
    return orders


def change_order_status_to_completed(order_id):
    """
    Изменение статуса заказа на "Completed".
    Возвращает tuple (order, error), где order - обновленный заказ,
    а error - сообщение об ошибке, если оно есть.
    """
    if not order_id:
        return None, "Необходимо передать order_id"

    try:
        order = Orders.objects.get(id=order_id)
        if order.status_orders != "Waiting":
            return None, "Заказ не находится в состоянии «Ожидание»."

        order.status_orders = "Completed"
        order.save()
        return order, None

    except Orders.DoesNotExist:
        return None, "Order not found"

    except Exception as e:
        return None, str(e)


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
