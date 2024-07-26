from rest_framework import serializers


class RefSystemSerializer(serializers.Serializer):
    user = serializers.DictField(
        label='Пользователь',
        help_text='Информация о пользователе, оформляющем заказ'
    )
