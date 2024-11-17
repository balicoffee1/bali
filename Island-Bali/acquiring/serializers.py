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
    
    

from rest_framework import serializers

class PaymentsRequestSerializer(serializers.Serializer):
    amount = serializers.IntegerField()
    currency = serializers.CharField(max_length=3, default='643')
    description = serializers.CharField(max_length=255, allow_blank=True)
    trans_id = serializers.CharField(max_length=28, allow_blank=True, required=False)


class RSBTransactionSerializer(serializers.Serializer):
    command = serializers.CharField(required=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    currency = serializers.CharField(required=True)
    description = serializers.CharField(required=False, default="Test transaction")