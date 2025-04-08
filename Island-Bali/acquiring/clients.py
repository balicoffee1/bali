import requests
import time
import uuid
from pathlib import Path
import os
from requests.auth import HTTPBasicAuth
import base64
from hashlib import sha256
from .base import BaseBankClient

BASE_DIR = Path(__file__).resolve().parent.parent
SSL_PATH = os.path.join(BASE_DIR, "cert")

TSP_ID = "9298136607"
TSP_KEY = "private.key"
TSP_PEM = "9298136607.pem"
CRT_CHAIN = "chain-ecomm-ca-root-ca.crt"


class RussianStandard:
    def __init__(self, user: str = 'demo', password: str = 'demo'):
        self._user = user
        self._password = password
        self._auth_data = HTTPBasicAuth(self._user, self._password)
        self._base_url = "https://demo.rsb-processing.ru"
        self._headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "Connection": "keep-alive"
        }

    def get(self, url: str, parameters: dict = None, json_data: dict = None):
        response = requests.get(
            url=self._base_url + url,
            headers=self._headers,
            json=json_data,
            auth=self._auth_data,
            params=parameters
        )
        return response.json()

    def link_for_payment(self, pay_amount: int, client_id: str, order_id: str,
                         client_email: str, service_name: str, client_phone: str,
                         url: str = '/change/invoice/preview/'):
        token_response = requests.get(
            url=self._base_url + "/info/settings/token/",
            headers=self._headers,
            auth=self._auth_data
        ).json()

        data_orders = {
            "pay_amount": pay_amount,
            "client_id": client_id,
            "order_id": order_id,
            "client_email": client_email,
            "service_name": service_name,
            "client_phone": client_phone,
            "token": token_response.get("token")
        }

        response = requests.post(
            url=self._base_url + url,
            headers=self._headers,
            auth=self._auth_data,
            data=data_orders
        )
        return response.json()

    def check_order(self, invoice_id: int):
        response = requests.get(
            url=self._base_url + f"/info/invoice/byid/?id={invoice_id}",
            headers=self._headers,
            auth=self._auth_data
        )
        return response.text




class AlphaBankClient(BaseBankClient):
    BASE_URL = 'https://baas.alfabank.ru/api/jp/v2'
    def __init__(self, api_token: str):
        self.api_token = api_token

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



class TinkoffClient(BaseBankClient):
    BASE_URL = 'https://secured-openapi.tbank.ru/api/v2/checkout'
    def __init__(self, api_token: str, shop_id: str):
        self.api_token = api_token
        self.shop_id = shop_id

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


class RSBClient:
    def __init__(self):
        self.host_rem_url = "https://testsecurepay2.rsb.ru:9443/ecomm2/MerchantHandler"
        self.redirect_url = "https://testsecurepay2.rsb.ru/ecomm2/ClientHandler?trans_id=transaction_id"
        self.ssl_path = SSL_PATH
        self.tsp_id = TSP_ID
        self.file_key = f"{self.ssl_path}/{TSP_KEY}"
        self.file_pem = f"{self.ssl_path}/{TSP_PEM}"
        self.file_cai = f"{self.ssl_path}/{CRT_CHAIN}"

    def generate_transaction_id(self):
        return f"{self.tsp_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    def send_request(self, command, amount, currency, description=None, trans_id=None, language="ru"):
        query_data = {
            "command": command,
            "amount": int(amount) * 100,
            "currency": int(currency),
            "client_ip_addr": "79.174.81.151",
            "description": description,
            "language": language,
            "mrch_transaction_id": self.generate_transaction_id(),
            "server_version": "2.0"
        }

        try:
            response = requests.post(
                url=self.host_rem_url,
                data=query_data,
                headers={"User-Agent": "Mozilla/5.0 Firefox/1.0.7"},
                cert=(self.file_pem, self.file_key),
                verify=self.file_cai,
                timeout=(5, 35)
            )

            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"{response.status_code} - {response.reason}"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}