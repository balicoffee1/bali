from rest_framework import serializers
from cart.models import CartItem, ShoppingCart
from menu_coffee_product.models import Product, Addon, AdditiveFlavors
from menu_coffee_product.serializers import ProductSerializer, AddonSerializer, AdditiveFlavorsSerializer

class CartItemAddonSerializer(serializers.ModelSerializer):
    flavors = serializers.SerializerMethodField()

    class Meta:
        model = Addon
        fields = ['id', 'name', 'description', 'price', 'coffee_shop', 'flavors']

    def get_flavors(self, obj):
        cart_item = self.context.get('cart_item')
        if cart_item:
            selected_flavors = cart_item.flavors.all()
            addon_flavors = obj.flavors.filter(id__in=[f.id for f in selected_flavors])
            return AdditiveFlavorsSerializer(addon_flavors, many=True).data
        return []

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    item_total_price = serializers.SerializerMethodField()
    addons = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ["id", 'product', 'amount', 'item_total_price', 'size', 'addons']

    def get_addons(self, obj):
        serializer = CartItemAddonSerializer(obj.addons.all(), many=True, context={'cart_item': obj})
        return serializer.data

    def get_item_total_price(self, obj):
        # ``item_total_price`` is a calculated property and therefore bypasses
        # DRF's DecimalField conversion.  REST responses used to hide that fact
        # because DRF's JSONRenderer knows how to encode Decimal, while Channels'
        # AsyncJsonWebsocketConsumer uses the standard json.dumps and crashed the
        # whole staff connection with code 1011.  Keep the wire format numeric —
        # the Flutter model calls ``toDouble()`` for this field.
        return float(obj.item_total_price)

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
    cart_item_id = serializers.IntegerField(required=False,
                                            help_text="ID элемента корзины")
    product_name = serializers.CharField(required=False,
                                         help_text="Введите имя продукта который хотите изменить",
                                         label="Введите имя продукта")
    quantity = serializers.IntegerField(required=True,
                                        help_text="Укажите количество",
                                        label="Количество товара")

    def validate(self, attrs):
        if not attrs.get('cart_item_id') and not attrs.get('product_name'):
            raise serializers.ValidationError("Необходимо указать cart_item_id или product_name")
        return attrs

class RemoveProductFromCartSerializer(serializers.Serializer):
    cart_item_id = serializers.IntegerField(required=False,
                                            help_text="ID элемента корзины")
    product_name = serializers.CharField(required=False,
                                         help_text="Введите имя продукта который хотите удалить",
                                         label="Введите имя продукта")

    def validate(self, attrs):
        if not attrs.get('cart_item_id') and not attrs.get('product_name'):
            raise serializers.ValidationError("Необходимо указать cart_item_id или product_name")
        return attrs


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
