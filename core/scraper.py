# core/scraper.py

import os
import requests
from bs4 import BeautifulSoup
from config import Config

class Scraper:

    @staticmethod
    def download_image(url, save_path):
        if not os.path.exists(save_path):
            try:
                response = requests.get(url, timeout=Config.REQUEST_TIMEOUT)
                if response.status_code == 200:
                    with open(save_path, 'wb') as f:
                        f.write(response.content)
                        print(f"Скачано изображение: {save_path}")
                else:
                    print(f"Не удалось скачать изображение: {url} (Статус: {response.status_code})")
            except requests.RequestException as e:
                print(f"Ошибка при скачивании изображения {url}: {e}")

    @staticmethod
    def scrape_icons():
        if not os.path.exists(Config.RESOURCES_DIR):
            os.makedirs(Config.RESOURCES_DIR)

        response = requests.get(Config.WEBSITE_BASE_URL)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Извлечение ссылок на иконки игр
            icons = soup.find_all('img', {'href': True})
            for icon in icons:
                icon_url = Config.WEBSITE_BASE_URL + icon['href'].replace('./', '/')
                icon_name = icon_url.split('/')[-1]
                save_path = os.path.join(Config.RESOURCES_DIR, icon_name)
                Scraper.download_image(icon_url, save_path)
