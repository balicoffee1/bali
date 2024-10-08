import qrcode
import io
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from coffee_shop.models import CoffeeShop
from subtotal_api.views import SubtotalClient
from quickresto.views import BalanceView
import json
import requests

layer_name = ''

class GenerateQRCodeView(APIView):
    def post(self, request):
        user = request.user
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')


        try:
            shop = CoffeeShop.objects.get(city__name=shop_city, street=shop_street)
            if shop.crm_system.name == "SubTotal":
                client = SubtotalClient(email=shop.email, password=shop.password)
                discount = None
                if client.login():
                    discount = client.get_discount_for_phone_number(user.login)
                

            qr_data = {
                "shop_id": shop.id,
                "shop_city": shop.city.name,
                "shop_street": shop.street,
                "user_id": user.id,
                "email": user.login,
                "discount": discount
            }

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(json.dumps(qr_data))
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            return HttpResponse(buffer, content_type="image/png")

        except CoffeeShop.DoesNotExist:
            return Response({"error": "Кофейня не найдена"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# def get_discount(shop, phone_number):
#     if shop.crm_system.name == "SubTotal":
#         client = SubtotalClient(email=shop.email, password=shop.password)
#         if client.login():
#             discount_value = client.get_discount_for_phone_number(phone_number)
#             if discount_value:
#                 return discount_value
#             else:
#                 return None, "Скидка не найдена"
#         else:
#             return None, "Ошибка авторизации в CRM системе"
#     elif shop.crm_system.name == "QuickRestoApi":
#         client = BalanceView()
#     else:
#         return None, "Неизвестная CRM система"

    

