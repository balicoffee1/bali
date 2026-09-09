from rest_framework import serializers

from .models import Addon, Category, Product, SeasonMenu
from .models import AdditiveFlavors

class AdditiveFlavorsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdditiveFlavors
        fields = ['id', 'name']


class AddonSerializer(serializers.ModelSerializer):
    flavors = AdditiveFlavorsSerializer(many=True, read_only=True)
    
    class Meta:
        model = Addon
        fields = ['id', 'name', 'description', 'price', "coffee_shop", "flavors"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        # color и icon могут прийти пустыми — тогда клиент берёт оформление
        # из своего локального набора. Раньше набор был единственным
        # источником: цвет плитки нельзя было поменять без пересборки.
        fields = ['id', 'name', 'color', 'icon']


class ProductSerializer(serializers.ModelSerializer):
    addons = AddonSerializer(many=True, read_only=True)
    coffee_shop = serializers.StringRelatedField()
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'product',
            'availability',
            'temperature_type',
            'addons',
            "coffee_shop",
            "category",
            "price_s",
            "price_m",
            "price_l"
            ]


class SeasonMenuSerializer(serializers.ModelSerializer):
    coffee_shop_id = serializers.PrimaryKeyRelatedField(source='coffee_shop', read_only=True)
    coffee_shop_name = serializers.StringRelatedField(source='coffee_shop')
    seasonal_section = serializers.CharField()
    season_display = serializers.CharField(source='get_season_display', read_only=True)
    # Вложенные товары только на чтение: писать состав раздела нужно через
    # список id, а не через развёрнутые объекты.
    products = ProductSerializer(many=True, read_only=True)

    class Meta:
        model = SeasonMenu
        fields = [
            'id', 'coffee_shop', 'coffee_shop_id', 'coffee_shop_name',
            'season', 'season_display', 'seasonal_section', 'is_active',
            'color', 'icon', 'products',
        ]
