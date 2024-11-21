import requests
from requests.auth import HTTPBasicAuth

# from island_bali import settings


class RussianStandard:
    def __init__(self, user: str = 'demo', password: str = 'demo'):
        self._user: str = user
        self._password: str = password
        self._auth_data: HTTPBasicAuth = HTTPBasicAuth(self._user,
                                                       self._password)
        # self._base_url = settings.RUSSIAN_STANDARD_BASE_URL
        self._base_url = "https://demo.rsb-processing.ru"
        self._headers: dict = {
            "Content-type": "application/x-www-form-urlencoded",
            "Connection": "keep-alive"
        }

    def get(self, url: str = '/info/systems/list/', parameters: dict = None,
            json_data: dict = None) -> requests.Response:
        response = requests.get(
            url=self._base_url + url,
            headers=self._headers,
            json=json_data,
            auth=self._auth_data,

            params=parameters
        )

        return response.json()

    def link_for_payment(self, pay_amount: int, client_id: str, order_id: str,
                         client_email: str, service_name: str,
                         client_phone: str,
                         url: str = '/change/'
                                    'invoice/preview/') -> requests.Response:
        get_token = requests.get(url=self._base_url + "/info/settings/token/",
                                 headers=self._headers,
                                 auth=self._auth_data).json()

        data_orders = {"pay_amount": pay_amount, "client_id": client_id,
                       "order_id": order_id,
                       "client_email": client_email,
                       "service_name": service_name,
                       "client_phone": client_phone,
                       "token": get_token["token"]}

        request = requests.post(url=self._base_url + url,
                                headers=self._headers, auth=self._auth_data,
                                data=data_orders)
        return request.json()

    def check_order(self, invoice_id: int):
        response = requests.get(
            url=self._base_url + f"/info/invoice/byid/?id={invoice_id}",
            headers=self._headers,
            auth=self._auth_data)
        return response.text


class AlfaBankService:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.alfabank.ru"
        self.token = None

    def authenticate(self):
        url = f"{self.base_url}/alfaid/oauth/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = requests.post(url, data=data, headers=headers)
        if response.status_code == 200:
            self.token = response.json().get("access_token")
        else:
            raise Exception("Ошибка аутентификации: " + response.text)

    def transfer(self, from_card: str, to_card: str, amount: int):
        if not self.token:
            self.authenticate()

        url = f"{self.base_url}/transfer/v1/payments"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        data = {
            "fromCardNumber": from_card,
            "toCardNumber": to_card,
            "amount": amount,
            "currencyCode": "RUB"
        }
        response = requests.post(url, json=data, headers=headers)
        return response.json()


class TinkoffBankService:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://securepay.tinkoff.ru"
        self.token = None

    def authenticate(self):
        url = f"{self.base_url}/oauth/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = requests.post(url, data=data, headers=headers)
        if response.status_code == 200:
            self.token = response.json().get("access_token")
        else:
            raise Exception("Ошибка аутентификации: " + response.text)

    def transfer(self, from_card: str, to_card: str, amount: int):
        if not self.token:
            self.authenticate()

        url = f"{self.base_url}/v1/payments"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        data = {
            "fromCardNumber": from_card,
            "toCardNumber": to_card,
            "amount": amount,
            "currencyCode": "RUB"
        }
        response = requests.post(url, json=data, headers=headers)
        return response.json()



import requests
import time
import uuid
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


SSL_PATH = os.path.join(BASE_DIR, "cert")
TSP_ID = "9298136607"  
TSP_KEY = "private.key"  
TSP_PEM = "9298136607.pem"  
CRT_CHAIN = "chain-ecomm-ca-root-ca.crt"


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
            "amount": int(amount)*100,
            "currency": int(currency),
            "client_ip_addr": "79.174.81.151",
            "description": description,
            "language": language,
            "mrch_transaction_id": self.generate_transaction_id(),
            "language": "ru",
            "server_version":"2.0"
        }


        # if trans_id:
        #     query_data["trans_id"] = trans_id

        try:
            response = requests.post(
                url=self.host_rem_url,
                data=query_data,
                headers={"User-Agent": "Mozilla/5.0 Firefox/1.0.7"},
                cert=(self.file_pem, self.file_key),  
                verify=self.file_cai,  
                timeout=(5, 35)  
            )
            
            # Логируем ответ
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"{response.status_code} - {response.reason}"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}