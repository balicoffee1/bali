from rest_framework import serializers

from coffee_shop.models import City, CoffeeShop


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ("id", "name",)


class CoffeeShopSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source="city.name", read_only=True)
    city_id = serializers.IntegerField(source="city.id", read_only=True)

    class Meta:
        model = CoffeeShop
        fields = (
            "id",
            "city_name",
            "street",
            "building_number",
            "time_open",
            "time_close",
            'city_id',
            "email",
            "telegram_username",
            "telegram_id",
            "crm_system",
            "acquiring",
            "inn",
            "phone_number",
        )
