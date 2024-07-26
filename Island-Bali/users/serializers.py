from rest_framework import serializers

from .models import CustomUser, UserCard


class UsersSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        exclude = ("password", "last_login")


class UserCardSerializer(serializers.ModelSerializer):
    card_number = serializers.SerializerMethodField()

    @staticmethod
    def get_card_number(obj):
        if obj.card_number:
            return obj.get_card_number()

    class Meta:
        model = UserCard
        fields = ["id", "user", "card_number", "expiration_date"]
