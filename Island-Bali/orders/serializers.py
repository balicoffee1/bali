from django.utils import timezone
from rest_framework import serializers

from acquiring.utils import RussianStandard
from cart.models import ShoppingCart
from users.models import CustomUser

from .models import Orders

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
        ]

    def validate_time_is_finish(self, value):
        now = timezone.now()
        if value < now:
            raise serializers.ValidationError(
                "Время завершения заказа не может быть в прошлом."
            )
        return value


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
        user_data = CustomUser.objects.get(id=user_id)
        cart = ShoppingCart.objects.get(user_id=user_id)
        phone_number_str = str(user_data.phone_number)
        total_cart_price = cart.cart_total_price
        payment_link = rus_standard.link_for_payment(
            total_cart_price,
            user_data.first_name,
            'Оплата заказа',
            user_data.email,
            'Оплата товаров',
            phone_number_str)
        return {
            'message': 'Заказ успешно оформлен.',
            'payment_link': payment_link
        }


class GetStatusPaymentSerializer(serializers.Serializer):
    invoice_id = serializers.CharField(
        label='Идентификатор счета',
        help_text='Идентификатор счета для получения статуса оплаты'
    )
