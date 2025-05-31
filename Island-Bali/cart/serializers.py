from rest_framework import serializers
from cart.models import CartItem, ShoppingCart
from menu_coffee_product.models import Product, Addon, AdditiveFlavors
from menu_coffee_product.serializers import ProductSerializer, AddonSerializer, AdditiveFlavorsSerializer

class CartItemSerializer(serializers.ModelSerializer):
    addons = AddonSerializer(many=True, read_only=True)
    product = ProductSerializer()
    item_total_price = serializers.SerializerMethodField()
    flavors = AdditiveFlavorsSerializer(many=True, read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", 'product', 'amount', 'item_total_price', 'size', 'addons', "flavors"]

    def get_item_total_price(self, obj):
        # product_price = obj.product.price
        # addons_price = sum(addon.price for addon in obj.addons.all())
        # total_price = (product_price + addons_price) * obj.amount
        return obj.item_total_price

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
    addons = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=Addon.objects.all()),
        required=False
    )
    size = serializers.ChoiceField(
        choices=CartItem.SizeChoices.choices,
        required=False,
        help_text="Введите размер продукта",  
        label="Выберите размер"
    )
    flavors = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=AdditiveFlavors.objects.all()),
        required=False,
        help_text="Список ID вкусов добавок"
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
        flavors_ids = validated_data.pop('flavors_ids', [])
        cart_item = CartItem.objects.create(**validated_data)
        cart_item.addons.set(addon_ids)
        cart_item.flavors.set(flavors_ids)
        return cart_item

    def update(self, instance, validated_data):
        addon_ids = validated_data.pop('addon_ids', [])
        flavors_ids = validated_data.pop('flavors_ids', [])
        instance.product = validated_data.get('product', instance.product)
        instance.amount = validated_data.get('amount', instance.amount)
        instance.size = validated_data.get('size', instance.size)
        instance.save()
        instance.addons.set(addon_ids)
        instance.flavors.set(flavors_ids)
        return instance


class UpdateCartItemSerializer(serializers.Serializer):
    cart_item_id = serializers.IntegerField(
        required=True,
        help_text="ID элемента корзины"
    )
    new_product_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID нового продукта (необязательно)"
    )
    quantity = serializers.IntegerField(
        required=True,
        help_text="Количество продукта (0 - удалить)"
    )
    size = serializers.ChoiceField(
        choices=CartItem.SizeChoices.choices,
        required=False,
        allow_null=True,
        help_text="Размер продукта: S, M, L"
    )
    temperature_type = serializers.ChoiceField(
        choices=Product.TEMPERATURE_TYPE_CHOICES,
        required=False,
        allow_null=True,
        help_text="Температура напитка: Hot или Cold"
    )
    addons = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="Список ID добавок"
    )
    flavors = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="Список ID вкусов"
    )

    def validate_new_product_id(self, value):
        if value:
            if not Product.objects.filter(id=value).exists():
                raise serializers.ValidationError("Продукт с указанным ID не найден")
        return value

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Количество не может быть отрицательным")
        return value
