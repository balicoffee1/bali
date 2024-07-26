from rest_framework import serializers

from .models import Addon, Category, Product, SeasonMenu


class AddonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Addon
        fields = '__all__'


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
        fields = '__all__'


class SeasonMenuSerializer(serializers.ModelSerializer):
    coffee_shop = serializers.StringRelatedField()
    seasonal_section = serializers.CharField()
    products = ProductSerializer(
        many=True)

    class Meta:
        model = SeasonMenu
        fields = '__all__'
