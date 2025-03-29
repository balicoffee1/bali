from rest_framework import serializers

from .models import Addon, Category, Product, SeasonMenu


class AddonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Addon
        fields = ['id', 'name', 'description', 'price', "coffee_shop"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class ProductSerializer(serializers.ModelSerializer):
    addon = AddonSerializer(many=True, read_only=True)
    coffee_shop = serializers.StringRelatedField()
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'product',
            'price',
            'availability',
            'temperature_type',
            'addon',
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
    products = ProductSerializer(
        many=True)

    class Meta:
        model = SeasonMenu
        fields = '__all__'
