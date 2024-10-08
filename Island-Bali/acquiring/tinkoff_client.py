import requests
from uuid import uuid4
from .base import BaseBankClient

class TinkoffClient(BaseBankClient):
    BASE_URL = 'https://secured-openapi.tbank.ru/api/v2/checkout'
    API_TOKEN = 'your_tinkoff_api_token'
    SHOP_ID = 'your_shop_id'

    @staticmethod
    def _get_headers():
        return {
            'Authorization': f'Bearer {TinkoffClient.API_TOKEN}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def create_order(self, order_data):
        url = f'{TinkoffClient.BASE_URL}/order'
        headers = TinkoffClient._get_headers()

        response = requests.post(url, json=order_data, headers=headers)
        response.raise_for_status()
        return response.json()

    def get_order(self, order_id):
        url = f'{TinkoffClient.BASE_URL}/order/{TinkoffClient.SHOP_ID}/by/{order_id}'
        headers = TinkoffClient._get_headers()

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
