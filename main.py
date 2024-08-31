# main.py

import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.scraper import Scraper

def main():
    # Скачиваем иконки при первом запуске
    Scraper.scrape_icons()

    # Создание приложения PyQt
    app = QApplication(sys.argv)

    # Создание главного окна
    main_window = MainWindow()
    main_window.show()

    # Запуск цикла приложения
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
