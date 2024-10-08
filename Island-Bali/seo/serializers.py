from rest_framework import serializers
from .models import ColorModel

class ColorModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColorModel
        fields = ['id', "title", 'color']
