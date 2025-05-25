from rest_framework import serializers
from orders.models import Orders
from .models import LifepayInvoice

class PaymentRequestSerializer(serializers.Serializer):
    amount = serializers.IntegerField(help_text="Сумма оплаты")
    client_id = serializers.CharField(max_length=255, help_text="Идентификатор клиента")
    order_id = serializers.CharField(max_length=255, help_text="Идентификатор заказа")
    client_email = serializers.EmailField(help_text="Электронная почта клиента")
    service_name = serializers.CharField(max_length=255, help_text="Название услуги")
    client_phone = serializers.CharField(max_length=20, help_text="Телефон клиента")

class PaymentResponseSerializer(serializers.Serializer):
    payment_url = serializers.URLField(help_text="Ссылка для перехода на страницу оплаты")
    transaction_id = serializers.CharField(required=False, allow_null=True)
    status = serializers.CharField(max_length=20, help_text="Статус оплаты")

class RSBTransactionSerializer(serializers.Serializer):
    command = serializers.CharField(max_length=50, help_text="Команда транзакции")
    amount = serializers.FloatField(help_text="Сумма транзакции")
    currency = serializers.CharField(max_length=3, help_text="Валюта транзакции")
    description = serializers.CharField(max_length=255, help_text="Описание транзакции")


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Orders
        fields = '__all__'


class LifepayInvoiceSerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)
    class Meta:
        model = LifepayInvoice
        fields = ['id', 'user', 'transaction_number', 'payment_url', 'payment_url_web', 'created_at', 'order']
        read_only_fields = ['id', 'user', 'transaction_number', 'payment_url', 'payment_url_web', 'created_at']