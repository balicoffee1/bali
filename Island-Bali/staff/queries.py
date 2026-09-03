"""
Единый источник правды о составе экрана смены (M7).

Раньше эти querysets жили прямо во вьюхах. Когда staff-экран переехал на
WebSocket, встал выбор: продублировать их в publisher'е — и получить два
источника правды о том, что видит бариста, — или вынести в общее место.
Вынесены сюда: и REST-ответы, и realtime-снапшот собираются из одних и тех же
функций, поэтому разъехаться не могут.

Сознательно сохранено текущее поведение, каким бы странным оно ни выглядело:
переезд на другой транспорт не должен незаметно менять то, что видит человек
на смене. Два момента, которые стоит знать и которые здесь НЕ исправлены:

* колонки Waiting / In Progress / Completed не ограничены по времени вообще —
  «Выполненные» растут бесконечно;
* агрегаты (счётчики и суммы) считаются по ВСЕЙ таблице заказов, без фильтра по
  кофейне и городу, то есть бариста видит цифры по всей сети.

И то и другое стоит починить, но отдельно и осознанно.
"""
from datetime import timedelta

from django.db import models

from orders.models import Orders

# Окно, в котором заказ считается актуальным для смены. Ровно это значение
# мобильное приложение раньше считало у себя и присылало параметром
# sorting_time — теперь оно живёт на сервере и одинаково для обоих транспортов.
SHIFT_WINDOW = timedelta(minutes=40)


def _scoped(queryset, *, city_id, coffee_shop_id):
    if city_id is not None:
        queryset = queryset.filter(city_choose=city_id)
    if coffee_shop_id is not None:
        queryset = queryset.filter(coffee_shop=coffee_shop_id)
    return queryset


def orders_in_shift_window(*, city_id, coffee_shop_id, sorting_time=None):
    """Заказы смены — то, что отдаёт GET /api/staff/orders/ в поле "orders"."""
    queryset = Orders.objects.all()
    if sorting_time:
        queryset = queryset.filter(time_is_finish__gte=sorting_time)
    queryset = _scoped(queryset, city_id=city_id, coffee_shop_id=coffee_shop_id)
    return queryset.order_by("time_is_finish", "-created_at")


def orders_with_status(*, city_id, coffee_shop_id, status):
    """Колонка по статусу — то, что отдаёт POST /api/staff/orders_by_status/."""
    queryset = Orders.objects.filter(status_orders=status)
    queryset = _scoped(queryset, city_id=city_id, coffee_shop_id=coffee_shop_id)
    return queryset.order_by("-created_at").prefetch_related("review")


def _money(value):
    """Decimal -> float.

    DRF отдаёт эти суммы числом (его JSON-энкодер приводит Decimal к float), а
    Channels сериализует обычным json.dumps, который на Decimal падает. Приводим
    здесь, чтобы оба транспорта отдавали одно и то же и клиенту не пришлось
    разбирать два формата.
    """
    return float(value) if value is not None else 0


def shift_aggregates():
    """Счётчики и суммы для карточки смены."""
    status_counts = {
        status: Orders.objects.filter(status_orders=status).count()
        for status in (Orders.WAITING, Orders.IN_PROGRESS, Orders.COMPLETED, Orders.CANCELED)
    }
    payment_totals = {
        status: _money(
            Orders.objects.filter(payment_status=status).aggregate(
                total=models.Sum("full_price")
            )["total"]
        )
        for status in (Orders.NEW, Orders.PENDING, Orders.PAID, Orders.FAILED)
    }
    order_totals = {
        status: _money(
            Orders.objects.filter(status_orders=status).aggregate(
                total=models.Sum("full_price")
            )["total"]
        )
        for status in (Orders.WAITING, Orders.IN_PROGRESS, Orders.COMPLETED, Orders.CANCELED)
    }
    return {
        "status_counts": status_counts,
        "payment_totals": payment_totals,
        "order_totals": order_totals,
    }
