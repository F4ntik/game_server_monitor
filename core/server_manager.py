# core/server_manager.py

import logging
from core.api_client import APIClient
from core.scraper import Scraper

class ServerManager:
    def __init__(self):
        self.servers = {}

    def load_servers(self):
        logging.info("Получение списка серверов")
        server_list = APIClient.get_server_list()
        logging.info(f"Найдено {len(server_list)} серверов")
        for game, ip_port in server_list.items():
            logging.info(f"Загрузка данных для сервера {ip_port}")
            server_data = APIClient.get_server_data(ip_port)
            if server_data:
                self.servers[ip_port] = server_data
                logging.info(f"Данные получены для сервера {ip_port}")
            else:
                logging.warning(f"Не удалось получить данные для сервера {ip_port}")

    def get_server_data(self, ip_port):
        return self.servers.get(ip_port, {})
