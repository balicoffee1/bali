import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from coffee_shop.models import CoffeeShop

layer_name = ''

class FilterCustomersView(APIView):
    def post(self, request):
        url = f"https://{layer_name}.quickresto.ru/platform/online/bonuses/filterCustomers"
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')
        shop = CoffeeShop.objects.get(city__name=shop_city,
                                          street=shop_street)
        auth = (shop.email, shop.password)

        data = {
            "search": request.data.get("search", "")
        }

        response = requests.post(url, json=data, headers=headers, auth=auth)

        return Response(response.json(), status=response.status_code)


class GetCustomerView(APIView):
    def post(self, request):
        url = f"https://{layer_name}.quickresto.ru/platform/online/bonuses/getCustomer"
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')
        shop = CoffeeShop.objects.get(city__name=shop_city,
                                          street=shop_street)
        auth = (shop.email, shop.password)

        data = {
            "customerToken": {
                "type": request.data.get("type", "card"),
                "entry": request.data.get("entry", "trackCode"),
                "key": request.data.get("key", "")
            }
        }

        response = requests.post(url, json=data, headers=headers, auth=auth)

        return Response(response.json(), status=response.status_code)

class BalanceView(APIView):
    def post(self, request):
        url = f"https://{layer_name}.quickresto.ru/platform/online/bonuses/balance"
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')
        shop = CoffeeShop.objects.get(city__name=shop_city,
                                          street=shop_street)
        auth = (shop.email, shop.password)

        data = {
            "customerToken": {
                "type": request.data.get("type", "card"),
                "entry": request.data.get("entry", "trackCode"),
                "key": request.data.get("key", "")
            },
            "accountType": {
                "accountGuid": request.data.get("accountGuid", "")
            }
        }

        response = requests.post(url, json=data, headers=headers, auth=auth)

        return Response(response.json(), status=response.status_code)


class OperationHistoryView(APIView):
    def post(self, request):
        url = f"https://{layer_name}.quickresto.ru/platform/online/bonuses/operationHistory"
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')
        shop = CoffeeShop.objects.get(city__name=shop_city,
                                          street=shop_street)
        auth = (shop.email, shop.password)

        data = {
            "customerToken": {
                "type": request.data.get("type", "card"),
                "entry": request.data.get("entry", "trackCode"),
                "key": request.data.get("key", "")
            },
            "accountType": {
                "accountGuid": request.data.get("accountGuid", "")
            }
        }

        response = requests.post(url, json=data, headers=headers, auth=auth)

        return Response(response.json(), status=response.status_code)


class DebitHoldView(APIView):
    def post(self, request):
        url = f"https://{layer_name}.quickresto.ru/platform/online/bonuses/debitHold"
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')
        shop = CoffeeShop.objects.get(city__name=shop_city,
                                          street=shop_street)
        auth = (shop.email, shop.password)

        data = {
            "customerToken": {
                "type": request.data.get("type", "card"),
                "entry": request.data.get("entry", "trackCode"),
                "key": request.data.get("key", "")
            },
            "accountType": {
                "accountGuid": request.data.get("accountGuid", "")
            },
            "amount": request.data.get("amount", 0),
            "date": request.data.get("date", ""),
            "precheck": request.data.get("precheck", "")
        }

        response = requests.post(url, json=data, headers=headers, auth=auth)

        return Response(response.json(), status=response.status_code)


class CreditHoldView(APIView):
    def post(self, request):
        url = f"https://{layer_name}.quickresto.ru/platform/online/bonuses/creditHold"
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')
        shop = CoffeeShop.objects.get(city__name=shop_city,
                                          street=shop_street)
        auth = (shop.email, shop.password)

        data = {
            "customerToken": {
                "type": request.data.get("type", "card"),
                "entry": request.data.get("entry", "trackCode"),
                "key": request.data.get("key", "")
            },
            "accountType": {
                "accountGuid": request.data.get("accountGuid", "")
            },
            "amount": request.data.get("amount", 0),
            "date": request.data.get("date", ""),
            "precheck": request.data.get("precheck", "")
        }

        response = requests.post(url, json=data, headers=headers, auth=auth)

        return Response(response.json(), status=response.status_code)


class ReverseView(APIView):
    def post(self, request):
        url = f"https://{layer_name}.quickresto.ru/platform/online/bonuses/reverse"
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')
        shop = CoffeeShop.objects.get(city__name=shop_city,
                                          street=shop_street)
        auth = (shop.email, shop.password)

        data = {
            "customerToken": {
                "type": request.data.get("type", "card"),
                "entry": request.data.get("entry", "trackCode"),
                "key": request.data.get("key", "")
            },
            "accountType": {
                "accountGuid": request.data.get("accountGuid", "")
            },
            "amount": request.data.get("amount", 0),
            "bonusTransactionId": request.data.get("bonusTransactionId", 0)
        }

        response = requests.post(url, json=data, headers=headers, auth=auth)

        return Response(response.json(), status=response.status_code)

class ReadCustomerView(APIView):
    def get(self, request):
        object_id = request.query_params.get("objectId")
        url = f"https://{layer_name}.quickresto.ru/platform/online/api/read?moduleName=crm.customer&className=ru.edgex.quickresto.modules.crm.customer.CrmCustomer&objectId={object_id}"
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')
        shop = CoffeeShop.objects.get(city__name=shop_city,
                                          street=shop_street)
        auth = (shop.email, shop.password)

        response = requests.get(url, headers=headers, auth=auth)

        return Response(response.json(), status=response.status_code)

class ListCustomersView(APIView):
    def get(self, request):
        url = "https://{layer_name}.quickresto.ru/platform/online/api/list?moduleName=crm.customer&className=ru.edgex.quickresto.modules.crm.customer.CrmCustomer"
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')
        shop = CoffeeShop.objects.get(city__name=shop_city,
                                          street=shop_street)
        auth = (shop.email, shop.password)

        response = requests.get(url, headers=headers, auth=auth)

        return Response(response.json(), status=response.status_code)

class CreateCustomerView(APIView):
    def post(self, request):
        url = f"https://{layer_name}.quickresto.ru/platform/online/api/create?moduleName=crm.customer&className=ru.edgex.quickresto.modules.crm.customer.CrmCustomer"
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')
        shop = CoffeeShop.objects.get(city__name=shop_city,
                                          street=shop_street)
        auth = (shop.email, shop.password)

        data = request.data

        response = requests.post(url, json=data, headers=headers, auth=auth)

        return Response(response.json(), status=response.status_code)

class UpdateCustomerView(APIView):
    def post(self, request):
        url = f"https://{layer_name}.quickresto.ru/platform/online/api/update?moduleName=crm.customer&className=ru.edgex.quickresto.modules.crm.customer.CrmCustomer"
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')
        shop = CoffeeShop.objects.get(city__name=shop_city,
                                          street=shop_street)
        auth = (shop.email, shop.password)

        data = request.data

        response = requests.post(url, json=data, headers=headers, auth=auth)

        return Response(response.json(), status=response.status_code)

class RemoveCustomerView(APIView):
    def post(self, request):
        url = f"https://{layer_name}.quickresto.ru/platform/online/api/remove?moduleName=crm.customer&className=ru.edgex.quickresto.modules.crm.customer.CrmCustomer"
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        shop_city = request.data.get('shop_city')
        shop_street = request.data.get('shop_street')
        shop = CoffeeShop.objects.get(city__name=shop_city,
                                          street=shop_street)
        auth = (shop.email, shop.password)

        data = {
            "objectId": request.data.get("objectId", "")
        }

        response = requests.post(url, json=data, headers=headers, auth=auth)

        return Response(response.json(), status=response.status_code)
