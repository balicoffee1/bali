import datetime

from django.core.exceptions import ValidationError

from coffee_shop.models import CoffeeShop


# def validate_time_is_finish(value):
#     now = datetime.datetime.now()
#     min_time = now + datetime.timedelta(minutes=5)
#     max_time = now + datetime.timedelta(minutes=25)

#     if not min_time <= value <= max_time:
#         raise ValidationError(
#             f'Время до получения заказа должно быть минимум через 5 минут '
#             f'и максимум через 25 минут от текущего времени. '
#             f'Вы выбрали {value}.')


# def validate_cafe_open_or_not(current_time: datetime, coffee_shop: CoffeeShop):
#     open_time = coffee_shop.time_open
#     open_close = coffee_shop.time_close
#     if open_time <= current_time < open_close:
#         return True
#     else:
#         return False
