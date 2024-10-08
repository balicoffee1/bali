from rest_framework import serializers

class PaymentRequestSerializer(serializers.Serializer):
    pay_amount = serializers.IntegerField()
    client_id = serializers.CharField(max_length=255)
    order_id = serializers.CharField(max_length=255)
    client_email = serializers.EmailField()
    service_name = serializers.CharField(max_length=255)
    client_phone = serializers.CharField(max_length=20)

class PaymentResponseSerializer(serializers.Serializer):
    invoice_id = serializers.CharField(max_length=255)
    invoice_url = serializers.URLField()
    invoice = serializers.CharField()
