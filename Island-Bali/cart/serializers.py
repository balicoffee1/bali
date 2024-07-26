from rest_framework import serializers

from cart.models import CartItem, ShoppingCart
from menu_coffee_product.models import Product
from menu_coffee_product.serializers import ProductSerializer


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer()

    class Meta:
        model = CartItem
        fields = ['product', 'amount', 'item_total_price']


class CartSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    items = CartItemSerializer(many=True)

    class Meta:
        model = ShoppingCart
        fields = "__all__"


class AddToCartSerializer(serializers.Serializer):
    product_name = serializers.CharField(required=True,
                                         help_text="Введите имя продукта "
                                                   "который хотите добавить",
                                         label="Введите имя продукта")
    quantity = serializers.IntegerField(required=True,
                                        help_text="Укажите количество",
                                        label="Количество товара")
    temperature_type = serializers.ChoiceField(
        choices=Product.TEMPERATURE_TYPE_CHOICES,
        required=False,
        help_text="Выберите тип температуры: холодный или горячий",
        label="Тип температуры напитка")
    addon = serializers.CharField(required=False,
                                  help_text="Добавка",
                                  label="Напишите добавку")


class ChangeCartSerializer(serializers.Serializer):
    product_name = serializers.CharField(required=True,
                                         help_text="Введите имя продукта "
                                                   "который хотите изменить",
                                         label="Введите имя продукта")
    quantity = serializers.IntegerField(required=True,
                                        help_text="Укажите количество",
                                        label="Количество товара")


class RemoveProductFromCartSerializer(serializers.Serializer):
    product_name = serializers.CharField(required=True,
                                         help_text="Введите имя продукта "
                                                   "который хотите удалить",
                                         label="Введите имя продукта")
