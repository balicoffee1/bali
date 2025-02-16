from rest_framework import serializers

from .models import ReviewsCoffeeShop
from coffee_shop.models import CoffeeShop
from orders.models import Orders


class ReviewsCoffeeShopSerializer(serializers.ModelSerializer):
    coffee_shop = serializers.PrimaryKeyRelatedField(
        queryset=CoffeeShop.objects.all(),
        label="Кофейня",
        help_text="Кофейня, в которой был сделан заказ"
    )
    user = serializers.StringRelatedField(label="Пользователь",
                                          help_text="Пользователь, "
                                                    "оставивший отзыв")
    orders = serializers.PrimaryKeyRelatedField(
        queryset=Orders.objects.all(),
        label="Отзыв к заказу",
        help_text="Отзыв к заказу"
    )
    evaluation = serializers.IntegerField(
        min_value=1,
        max_value=5,
        label="Оценка",
        help_text="Оценка, выставленная пользователем от 1 до 5."
    )
    very_tasty = serializers.BooleanField(
        required=False,
        label="Очень вкусно",
        help_text="Показатель, указывающий, что пользователю очень понравился "
                  "вкус кофе в кофейне."
    )
    wide_range = serializers.BooleanField(
        required=False,
        label="Широкий ассортимент",
        help_text="Показатель, указывающий, что пользователю понравился "
                  "широкий ассортимент кофе в кофейне."
    )
    nice_prices = serializers.BooleanField(
        required=False,
        label="Хорошие цены",
        help_text="Показатель, указывающий, что пользователю "
                  "понравились хорошие цены в кофейне."
    )
    comments = serializers.CharField(
        required=False,
        allow_blank=True,
        label="Комментарии",
        help_text="Дополнительные комментарии или отзыв пользователя о "
                  "кофейне."
    )

    class Meta:
        model = ReviewsCoffeeShop
        fields = (
            "id", "coffee_shop", "user", "orders", "evaluation", "very_tasty",
            "wide_range", "nice_prices", "comments"
        )
