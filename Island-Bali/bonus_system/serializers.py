from rest_framework import serializers

from .models import DiscountCard


class DiscountCardSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели DiscountCard.
    """

    class Meta:
        model = DiscountCard
        fields = "__all__"
