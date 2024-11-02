from rest_framework import serializers

from coffee_shop.models import City, CoffeeShop


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ("name",)


class CoffeeShopSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source="city.name", read_only=True)

    class Meta:
        model = CoffeeShop
        fields = (
            "id",
            "city_name",
            "street",
            "building_number",
            "lat",
            "lon"
        )
