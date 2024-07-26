import requests
from requests.auth import HTTPBasicAuth

from island_bali import settings


class RussianStandard:
    def __init__(self, user: str = 'demo', password: str = 'demo'):
        self._user: str = user
        self._password: str = password
        self._auth_data: HTTPBasicAuth = HTTPBasicAuth(self._user,
                                                       self._password)
        self._base_url = settings.RUSSIAN_STANDARD_BASE_URL
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


rus_standard = RussianStandard()
req = rus_standard.link_for_payment(42,
                                    'Иванов Иван Иваныч',
                                    'Заказ № 10',
                                    'test@example.com',
                                    'Услуга',
                                    '8 (910) 123-45-67')
