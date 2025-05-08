from rest_framework import serializers
from .models import ColorModel, MarkdownModel

class ColorModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColorModel
        fields = ['id', "title", 'color']


class MarkdownModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarkdownModel
        fields = ['id', "title", 'text']