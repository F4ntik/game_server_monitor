class Config:
    # Базовый URL для API
    API_BASE_URL = "http://gamestates.ru:8000/"

    # URL основного сайта
    WEBSITE_BASE_URL = "https://gamestates.ru"

    # Директория для сохранения ресурсов (иконок и карт)
    RESOURCES_DIR = "resources"

    # Таймаут для запросов к API (в секундах)
    REQUEST_TIMEOUT = 5

    # Период обновления данных о серверах (в секундах)
    SERVER_UPDATE_INTERVAL = 60
