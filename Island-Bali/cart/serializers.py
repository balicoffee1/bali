from rest_framework import serializers
from cart.models import CartItem, ShoppingCart
from menu_coffee_product.models import Product, Addon
from menu_coffee_product.serializers import ProductSerializer, AddonSerializer

class CartItemSerializer(serializers.ModelSerializer):
    addons = AddonSerializer(many=True, read_only=True)
    product = ProductSerializer()
    item_total_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['product', 'amount', 'item_total_price', 'size', 'addons']

    def get_item_total_price(self, obj):
        product_price = obj.product.price
        addons_price = sum(addon.price for addon in obj.addons.all())
        total_price = (product_price + addons_price) * obj.amount
        return total_price

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
    size = serializers.ChoiceField(
        choices=CartItem.SizeChoices.choices,
        required=False,
        help_text="Введите размер продукта",  
        label="Выберите размер"
    )

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


class CartItemCreateUpdateSerializer(serializers.ModelSerializer):
    addon_ids = serializers.PrimaryKeyRelatedField(queryset=Addon.objects.all(), many=True, write_only=True)

    class Meta:
        model = CartItem
        fields = ['product', 'amount', 'size', 'addon_ids']

    def create(self, validated_data):
        addon_ids = validated_data.pop('addon_ids', [])
        cart_item = CartItem.objects.create(**validated_data)
        cart_item.addons.set(addon_ids)
        return cart_item

    def update(self, instance, validated_data):
        addon_ids = validated_data.pop('addon_ids', [])
        instance.product = validated_data.get('product', instance.product)
        instance.amount = validated_data.get('amount', instance.amount)
        instance.size = validated_data.get('size', instance.size)
        instance.save()
        instance.addons.set(addon_ids)
        return instance
