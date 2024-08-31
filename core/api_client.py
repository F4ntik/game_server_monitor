# core/api_client.py

import requests
from config import Config

class APIClient:

    @staticmethod
    def get_server_list():
        try:
            response = requests.get(Config.API_BASE_URL, timeout=Config.REQUEST_TIMEOUT)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Ошибка при запросе списка серверов: {response.status_code}")
        except requests.RequestException as e:
            print(f"Ошибка подключения к API: {e}")
        return {}

    @staticmethod
    def get_server_data(ip_port):
        try:
            response = requests.get(f"{Config.API_BASE_URL}{ip_port}", timeout=Config.REQUEST_TIMEOUT)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Ошибка при запросе данных сервера {ip_port}: {response.status_code}")
        except requests.RequestException as e:
            print(f"Ошибка подключения к API: {e}")
        return None
