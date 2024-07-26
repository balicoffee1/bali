from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers

from .models import FranchiseInfo, FranchiseRequest


class FranchiseRequestSerializer(serializers.ModelSerializer):
    number_phone = PhoneNumberField(region="RU")

    class Meta:
        model = FranchiseRequest
        fields = ("id", "name", "number_phone", "text")


class FranchiseInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = FranchiseInfo
        fields = ("text",)
