from rest_framework import serializers

from cart.serializers import CartSerializer
from users.serializers import UsersSerializer
from orders.models import Orders
from staff.models import Shift
from coffee_shop.serializers import CoffeeShopSerializer
from staff.models import Staff


class PendingOrdersAcceptSerializer(serializers.ModelSerializer):
    cart = CartSerializer(read_only=True, help_text="Информация о корзине "
                                                    "заказа")
    user_id = serializers.IntegerField(
        source='user.id', read_only=True, help_text="ID пользователя")
    login = serializers.CharField(source="user.login",  read_only=True, help_text="Номер телефона пользователя")

    class Meta:
        model = Orders
        fields = ("id", "user_id", "cart", "time_is_finish", "status_orders",
                  "client_comments", "payment_status", "receipt_photo", "staff_comments", "updated_time",
                "updated_at", "created_at", "client_confirmed",
                "is_used_discount", "login", "cancellation_reason", "full_price", "checkLoaded", "issued", "is_appreciated", "is_updated")


class StaffSerializer(serializers.ModelSerializer):
    user = UsersSerializer(
        read_only=True, help_text="Информация о сотруднике",
        source='users'
    )
    coffee_shop = CoffeeShopSerializer(
        read_only=True, help_text="Информация о кофейне",
        source='place_of_work'
    )
    
    class Meta:
        model = Staff
        fields = "__all__"


class CreateOrderSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(help_text="ID заказа",
                                        label="ID заказа")


class PatchOrderSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(
        required=True,
        help_text="ID заказа",
        label="Order ID"
    )
    new_time_to_finish = serializers.DateTimeField(
        required=False,
        help_text="Новое время окончания заказа",
        label="New Time to Finish"
    )
    new_comments = serializers.CharField(
        required=False,
        help_text="Новый комментарий к заказу",
        label="New Comments"
    )
    created_at = serializers.DateTimeField(
        required=False,
        help_text="Дата создания заказа",
        label="Created At"
    )
    updated_at = serializers.DateTimeField(
        required=False,
        help_text="Дата обновления заказа",
        label="Updated At"
    )
    def update_order(self, instance, validated_data):
        """
        M7: updated_time/cancellation_reason больше не пишутся голым instance.save().

        Это единственные поля здесь, которые видит клиент и по которым он принимает
        решение показать диалог («бариста изменил время»), — а голый save() не
        публиковал WebSocket-событие, из-за чего диалог появлялся только на
        следующем тике 5-секундного polling'а. После отказа от polling'а он не
        появлялся бы вовсе, поэтому они уходят через OrderStateService.update_presentation,
        которое инкрементирует event_seq и публикует событие после commit.
        """
        from orders.services import OrderStateService

        presentation = {}
        if new_time_to_finish := validated_data.get('new_time_to_finish'):
            presentation['updated_time'] = new_time_to_finish
        if new_comments := validated_data.get('new_comments'):
            presentation['cancellation_reason'] = new_comments

        local_fields = []
        if created_at := validated_data.get('created_at'):
            instance.created_at = created_at
            local_fields.append('created_at')
        if updated_at := validated_data.get('updated_at'):
            instance.updated_at = updated_at
            local_fields.append('updated_at')
        # Сначала локальные поля, потом presentation — чтобы опубликованный
        # снапшот уже включал в себя всё изменённое этим запросом.
        if local_fields:
            instance.save(update_fields=local_fields)

        if presentation:
            instance = OrderStateService.update_presentation(
                instance.pk, actor_type="staff", **presentation
            )
        return instance


class CancelOrderSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(help_text="ID заказа",
                                        label="ID заказа")
    cancellation_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Комментарии персонала",
        label="Комментарии персонала"
    )


class CompleteOrdersSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(help_text="ID заказа",
                                        label="ID заказа")


class FilterOrdersByStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Orders.StatusOrders)


class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = ['id', 'staff', 'start_time', 'end_time',
                  'number_orders_closed', 'amount_closed_orders',
                  'status_shift']


class ShiftToggleRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()


class ShiftToggleResponseSerializer(serializers.Serializer):
    status_shift = serializers.CharField()
    users = serializers.CharField()


class UploadReceiptPhotoRequestSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()


class UploadReceiptPhotoResponseSerializer(serializers.Serializer):
    photo_url = serializers.URLField()
