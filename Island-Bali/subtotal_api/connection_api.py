import os

import pandas as pd
import requests


class SubtotalClient:
    def __init__(self, email, password):
        self.session = requests.Session()
        self.base_url = "https://app.subtotal.ru"
        self.auth_url = f"{self.base_url}/webapi/login"
        self.email = email
        self.password = password
        self.owner = None

    def login(self):
        auth_data = {'login': self.email, 'password': self.password}
        response = self.session.post(self.auth_url, json=auth_data)
        if response.status_code == 200:
            self.owner = response.json().get('last_owner')
            return True
        return False

    def download_partners_file(self, filename='partners.xlsx'):
        if self.owner is None:
            raise Exception("Необходимо сначала авторизоваться.")

        folder_path = os.path.join(os.getcwd(), self.owner)

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        file_path = os.path.join(folder_path, filename)
        file_download_url = (f"{self.base_url}/{self.owner}"
                             f"/partner/list.php?/page_num=1&page_"
                             f"size=100000&filter_text=&show_archive="
                             f"false&filter_pos=&show_service=0&render_"
                             f"to=xls")
        response = self.session.get(file_download_url)
        if response.status_code == 200:
            with open(file_path, 'wb') as file:
                file.write(response.content)
            return file_path
        return None

    def get_discount_for_phone_number(self, phone_number):
        if self.owner is None:
            raise Exception("Необходимо сначала авторизоваться.")

        file_path = self.download_partners_file()

        if file_path is not None:
            df = pd.read_excel(file_path)
        
            phone_number = str(phone_number)
            phone_number = ''.join(
                [char for char in phone_number if char.isdigit()]) + ".0"

            result = df[df['Телефон'].astype(str) == phone_number][
                'Скидка клиента, %']
            
            if not result.empty and not result.isna().all():
                result = result.tolist()
                return f"{result}"
            else:
                return None
        else:
            return None


# client = SubtotalClient('tima.j.zh@gmail.com', 'c0llecti0n')
# if client.login():
#     phone_to_search = "79262229568"
#     discount_value = client.get_discount_for_phone_number(phone_to_search)

#     if discount_value is not None:
#         print(f"Скидка для клиента с номером телефона {phone_to_search}: "
#               f"{discount_value}%")
#     else:
#         print(f"Клиент с номером телефона {phone_to_search} "
#               f"не найден или скидка не указана.")
# else:
#     print("Ошибка авторизации.")