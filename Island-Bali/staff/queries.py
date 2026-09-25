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


def _resolve_shift_window(*, coffee_shop_id=None, shift=None):
    """
    Возвращает (shift_start, active_shift).
    Если передана или найдена открытая смена кофейни, берём shift.start_time.
    Иначе, если кофейня задана, берём начало текущих суток, чтобы бариста видел
    сегодняшние заказы.
    Если кофейня не задана (тесты/fallback), возвращаем (None, None).
    """
    if shift is not None:
        return shift.start_time, shift

    if coffee_shop_id is not None:
        from staff.models import Shift

        active_shift = (
            Shift.objects.filter(
                staff__place_of_work_id=coffee_shop_id,
                status_shift="Open",
            )
            .order_by("-start_time")
            .first()
        )
        if active_shift and active_shift.start_time:
            return active_shift.start_time, active_shift
        from django.utils import timezone

        start_of_day = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return start_of_day, None

    return None, None


def orders_with_status(*, city_id, coffee_shop_id, status, shift_start_time=None):
    """Колонка по статусу — то, что отдаёт POST /api/staff/orders_by_status/ и WS snapshot."""
    queryset = Orders.objects.filter(status_orders=status)
    queryset = _scoped(queryset, city_id=city_id, coffee_shop_id=coffee_shop_id)

    # Завершённые заказы ограничиваем окном смены (или сегодняшним днём),
    # чтобы список не рос бесконечно и совпадал со счётчиками смены.
    if status == Orders.COMPLETED:
        if shift_start_time is None and coffee_shop_id is not None:
            shift_start_time, _ = _resolve_shift_window(coffee_shop_id=coffee_shop_id)
        if shift_start_time is not None:
            queryset = queryset.filter(updated_at__gte=shift_start_time)

    return queryset.order_by("-created_at").prefetch_related("review")


def _money(value):
    """Decimal -> float.

    DRF отдаёт эти суммы числом (его JSON-энкодер приводит Decimal к float), а
    Channels сериализует обычным json.dumps, который на Decimal падает. Приводим
    здесь, чтобы оба транспорта отдавали одно и то же и клиенту не пришлось
    разбирать два формата.
    """
    return float(value) if value is not None else 0.0


def shift_aggregates(*, coffee_shop_id=None, shift=None):
    """Счётчики и суммы для карточки смены.

    Считаются строго в рамках кофейни и текущей смены (или текущих суток).
    """
    from decimal import Decimal
    from django.db.models.functions import Coalesce

    shift_start, _ = _resolve_shift_window(coffee_shop_id=coffee_shop_id, shift=shift)

    base_qs = Orders.objects.all()
    if coffee_shop_id is not None:
        base_qs = base_qs.filter(coffee_shop_id=coffee_shop_id)

    # Waiting и In Progress — это текущие активные заказы на точке
    waiting_qs = base_qs.filter(status_orders=Orders.WAITING)
    in_progress_qs = base_qs.filter(status_orders=Orders.IN_PROGRESS)

    # Completed и Canceled — заказы текущей смены
    completed_qs = base_qs.filter(status_orders=Orders.COMPLETED)
    canceled_qs = base_qs.filter(status_orders=Orders.CANCELED)

    if shift_start is not None:
        completed_qs = completed_qs.filter(updated_at__gte=shift_start)
        canceled_qs = canceled_qs.filter(updated_at__gte=shift_start)

    status_counts = {
        Orders.WAITING: waiting_qs.count(),
        Orders.IN_PROGRESS: in_progress_qs.count(),
        Orders.COMPLETED: completed_qs.count(),
        Orders.CANCELED: canceled_qs.count(),
    }

    # Payment totals: по заказам текущей смены
    payment_qs = base_qs
    if shift_start is not None:
        payment_qs = payment_qs.filter(updated_at__gte=shift_start)

    payment_totals = {
        p_status: _money(
            payment_qs.filter(payment_status=p_status).aggregate(
                total=Coalesce(models.Sum("full_price"), Decimal("0.00"))
            )["total"]
        )
        for p_status in (Orders.NEW, Orders.PENDING, Orders.PAID, Orders.FAILED)
    }

    order_totals = {
        Orders.WAITING: _money(
            waiting_qs.aggregate(
                total=Coalesce(models.Sum("full_price"), Decimal("0.00"))
            )["total"]
        ),
        Orders.IN_PROGRESS: _money(
            in_progress_qs.aggregate(
                total=Coalesce(models.Sum("full_price"), Decimal("0.00"))
            )["total"]
        ),
        Orders.COMPLETED: _money(
            completed_qs.aggregate(
                total=Coalesce(models.Sum("full_price"), Decimal("0.00"))
            )["total"]
        ),
        Orders.CANCELED: _money(
            canceled_qs.aggregate(
                total=Coalesce(models.Sum("full_price"), Decimal("0.00"))
            )["total"]
        ),
    }

    return {
        "status_counts": status_counts,
        "payment_totals": payment_totals,
        "order_totals": order_totals,
    }
