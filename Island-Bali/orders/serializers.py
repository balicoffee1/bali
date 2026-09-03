from django.utils import timezone
from rest_framework import serializers

from acquiring.clients import RussianStandard
from cart.models import ShoppingCart
from coffee_shop.models import City, CoffeeShop
from users.models import CustomUser

from .models import Orders, Notification, CheckOrder
from cart.serializers import CartSerializer

rus_standard = RussianStandard()


class OrdersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Orders
        fields = [
            "id",
            "user",
            "cart",
            "city_choose",
            "coffee_shop",
            "client_comments",
            "staff_comments",
            "time_is_finish",
            "staff",
            "payment_status",
            "status_orders",
            "receipt_photo"
        ]


class OrdersCreateSerializer(serializers.Serializer):
    client_comments = serializers.CharField(
        label='Комментарий',
        help_text='Комментарий к заказу',
        required=True
    )
    time_is_finish = serializers.DateTimeField(
        format='%Y-%m-%d %H:%M:%S',
        label='Время окончания выполнения заказа',
        help_text='Формат: YYYY-MM-DD HH:MM:SS'
    )


class CheckoutSerializer(serializers.Serializer):
    user = serializers.DictField(
        label='Пользователь',
        help_text='Информация о пользователе, оформляющем заказ'
    )

    def create(self, validated_data):
        user_data = validated_data.get('user')
        user_id = user_data.get('id')
        user = CustomUser.objects.get(id=user_id)
        cart = ShoppingCart.objects.get(user_id=user_id, is_active=True)

        if not cart.items.exists():
            raise serializers.ValidationError("Корзина пуста")

        # Создаем заказ
        order = cart.send_orders_for_confirmation_to_barista(
            user=user,
            city_choose=cart.city,
            coffee_shop=cart.coffee_shop,
            client_comments="",
            cart=cart
        )

        # Генерация ссылки на оплату
        payment_link = rus_standard.link_for_payment(
            cart.cart_total_price,
            user.first_name,
            'Оплата заказа',
            user.email,
            'Оплата товаров',
            str(user.phone_number)
        )

        # Переводим заказ в статус "Ожидание оплаты"
        order.payment_status = "Pending"
        order.save()

        # M7: этот путь создания заказа (POST /api/orders/checkout/) идёт мимо
        # OrderViewSet.perform_create, поэтому событие о создании нужно
        # опубликовать здесь — иначе клиент об этом заказе не узнает вовсе.
        from orders.services import OrderStateService

        OrderStateService.order_created(order.id)

        return {
            'message': 'Заказ успешно оформлен.',
            'payment_link': payment_link
        }


class GetStatusPaymentSerializer(serializers.Serializer):
    invoice_id = serializers.CharField(
        label='Идентификатор счета',
        help_text='Идентификатор счета для получения статуса оплаты'
    )




# M7: единый список полей заказа для клиента-покупателя. Из него собираются и REST
# (OrderSerializers, + cart_data), и WebSocket-снапшот (OrderRealtimeSerializer) — так
# они не могут разъехаться при добавлении поля, а мобильный OrderView.fromJson остаётся
# единственным парсером на обе стороны.
CUSTOMER_ORDER_FIELDS = [
    "id", "user", "city_choose", "coffee_shop", "cart", "client_comments",
    "staff_comments", "time_is_finish", "staff", "status_orders",
    "payment_status", "receipt_photo", "created_at", "updated_at", "updated_time", "issued",
    "full_price", "cancellation_reason", "client_confirmed", "is_appreciated",
    "city_choose_name", "coffee_shop_name", "is_updated",
    "is_used_discount", "is_testing", "version", "event_seq", "acknowledged_dialogs",
]


class AcknowledgedDialogsField(serializers.Field):
    """
    Список ключей подтверждённых диалогов — read-only проекция OrderDialogAck.

    Едет внутри самого заказа, а не отдельным событием: снапшот читается из БД в
    момент публикации, поэтому свежий ack оказывается в ближайшем же кадре сам,
    без отдельного типа сообщения.
    """
    def __init__(self, **kwargs):
        kwargs.setdefault("read_only", True)
        kwargs.setdefault("source", "*")
        super().__init__(**kwargs)

    def to_representation(self, order):
        # prefetch_related('dialog_acks') в queryset'е делает это без N+1
        return sorted(ack.dialog_key for ack in order.dialog_acks.all())


class OrderSerializers(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all(), required=False)
    staff = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all(), required=False)
    city_choose = serializers.PrimaryKeyRelatedField(queryset=City.objects.all())
    coffee_shop = serializers.PrimaryKeyRelatedField(queryset=CoffeeShop.objects.all())
    cart = serializers.PrimaryKeyRelatedField(queryset=ShoppingCart.objects.all(), required=False)
    cart_data = CartSerializer(source='cart', read_only=True)
    city_choose_name = serializers.CharField(source='city_choose.name', read_only=True)
    coffee_shop_name = serializers.StringRelatedField(source='coffee_shop')
    # M5 (mobile realtime reconciliation): read-only — mobile compares this against the
    # WebSocket event's version to decide whether a REST refresh is needed (never a write
    # vector; OrderStateService.orders/services.py remains the only place version changes).
    version = serializers.IntegerField(read_only=True)
    # M7: версия ленты событий — по ней клиент отбрасывает дубли и опоздавшие
    # WebSocket-события. Read-only: двигается только внутри OrderStateService.
    event_seq = serializers.IntegerField(read_only=True)
    acknowledged_dialogs = AcknowledgedDialogsField()

    class Meta:
        model = Orders
        fields = CUSTOMER_ORDER_FIELDS + ["cart_data"]
        



class OrderRealtimeSerializer(serializers.ModelSerializer):
    """
    Полезная нагрузка WebSocket-события для клиента-покупателя (M7, шаг 2).

    Тот же набор полей, что и у REST-списка заказов, минус cart_data: состав корзины
    весит больше всего остального payload'а вместе взятого (вложенный CartSerializer
    с items/products/addons), а мобильное приложение его нигде не читает — поле
    парсится в OrderView.cartData и не используется ни одним виджетом. REST его
    пока отдаёт, чтобы не ломать существующих потребителей.

    Наследуется от того же CUSTOMER_ORDER_FIELDS, что и OrderSerializers, — списки
    полей не могут разъехаться, а значит мобильный OrderView.fromJson одинаково
    разбирает и REST-ответ, и WebSocket-кадр.
    """
    city_choose_name = serializers.CharField(source='city_choose.name', read_only=True)
    coffee_shop_name = serializers.StringRelatedField(source='coffee_shop')
    acknowledged_dialogs = AcknowledgedDialogsField()

    class Meta:
        model = Orders
        fields = CUSTOMER_ORDER_FIELDS
        read_only_fields = CUSTOMER_ORDER_FIELDS


class NotificationSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all())

    class Meta:
        model = Notification
        fields = ['id', 'order', 'user', 'message', 'is_read', 'created_at']
        


class OrderStatusUpdateSerializer(serializers.Serializer):
    """
    M1 п.18: раньше был ModelSerializer с полем status_orders — то есть любое
    допустимое значение из StatusOrders можно было записать напрямую через
    serializer.save(), в обход state machine (в т.ч. можно было выставить
    заказу себе "Completed"/"Paid" без реального перехода). Теперь это чистый
    валидатор, значение передаётся в OrderStateService конкретным именованным
    методом (accept/cancel/complete) — см. OrderStatusUpdateView.
    """
    status_orders = serializers.ChoiceField(choices=Orders.StatusOrders)


class OrderTimeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Orders
        fields = ['time_is_finish']


class PaymentSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(choices=[('СБП', 'СБП'), ('Эквайринг', 'Эквайринг')])

    def validate_payment_method(self, value):
        if value not in ['СБП', 'Эквайринг']:
            raise serializers.ValidationError('Неверный метод оплаты')
        return value


class CheckOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckOrder
        fields = ['id', 'order', 'check_photo', 'created_at']
        

class StaffOrderUpdateSerializer(serializers.ModelSerializer):
    """
    M0 п.3.3 / M1 п.18: раньше exclude=['user','created_at','cart'] делал
    ЛЮБОЕ остальное поле — включая status_orders, payment_status, version,
    staff, coffee_shop, full_price — доступным для прямой записи через один
    PATCH без какой-либо проверки допустимости перехода (P0 в исходном
    аудите). Теперь этот serializer явно ограничен presentation/операционными
    полями, не входящими в две state machine; изменение status_orders/
    payment_status здесь больше невозможно в принципе.
    """
    class Meta:
        model = Orders
        fields = [
            'client_comments', 'staff_comments', 'time_is_finish',
            'receipt_photo', 'is_appreciated', 'is_updated',
        ]