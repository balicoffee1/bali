import requests
import base64
import json
from hashlib import sha256
from uuid import uuid4
from .base import BaseBankClient

class AlphaBankClient(BaseBankClient):
    BASE_URL = 'https://baas.alfabank.ru/api/jp/v2'
    API_TOKEN = 'your_alpha_bank_api_token'

    @staticmethod
    def _get_headers():
        return {
            'Authorization': f'Bearer {AlphaBankClient.API_TOKEN}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def create_payment_order(self, payment_data):
        url = f'{AlphaBankClient.BASE_URL}/payments'
        headers = AlphaBankClient._get_headers()

        response = requests.post(url, json=payment_data, headers=headers)
        response.raise_for_status()
        return response.json()

    def get_payment_status(self, external_id):
        url = f'{AlphaBankClient.BASE_URL}/payments/{external_id}/state'
        headers = AlphaBankClient._get_headers()

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def sign_data(self, data):
        hash_string = '&'.join(f'{key}={value}' for key, value in sorted(data.items()))
        digest = sha256(hash_string.encode()).digest()
        signature = base64.b64encode(digest).decode()
        return signature
