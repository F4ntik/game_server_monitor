import sys
import os
import logging
import requests
import json
import copy
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QMainWindow,
    QSystemTrayIcon, QMenu, QDialog, QCheckBox, QSpinBox, QStyle, QSizePolicy,
    QSlider, QGridLayout, QGroupBox, QStyleOptionSizeGrip, QMessageBox
)
from PyQt6.QtGui import QIcon, QPixmap, QAction, QCursor, QPainter, QColor
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QTimer, QThread, QObject, pyqtSlot, QSize, QPoint
)
from ping3 import ping
from ping3.errors import PingError
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker # Added for custom tick formatting

class PingWorker(QObject):
    """Рабочий поток для выполнения ping-запросов."""
    ping_result = pyqtSignal(int)
    ping_failed = pyqtSignal()

    def __init__(self, address):
        """Инициализирует PingWorker с заданным адресом.

        :param address: Адрес для выполнения ping-запроса.
        """
        super().__init__()
        self.address = address

    def run(self):
        """Запускает ping-запрос к заданному адресу и передает результат."""
        try:
            if not self.address: # Ensure address is not None or empty
                logging.error("PingWorker.run() called with no address.")
                self.ping_failed.emit()
                return

            response = ping(self.address, timeout=2) # ping3.ping call, unit 's'

            # ping3 returns: delay (float in s), False (timeout), or None (error)
            if response is not None and response is not False: # Check for actual delay value
                self.ping_result.emit(int(response * 1000)) # Convert to ms
            else:
                if response is False: # Explicitly a timeout from ping3
                    logging.warning(f"Ping timed out for address {self.address} after 2 seconds.")
                elif response is None: # Other errors like host unknown (can also raise PingError)
                     logging.warning(f"Ping returned None (possibly host unknown or other network error) for address {self.address}.")
                # else: # Should not happen based on ping3 docs if strictly None/False/float
                #      logging.warning(f"Ping returned unexpected value '{response}' for address {self.address}.")
                self.ping_failed.emit()
        except PingError as e: # Specific exception from ping3
            logging.error(f"Ping failed for address {self.address} with PingError: {e}. This could be due to DNS issues, network configuration, or permissions (e.g., needing root/CAP_NET_RAW for ICMP).")
            self.ping_failed.emit()
        except Exception as e: # Catch any other unexpected error during ping process
            logging.error(f"Unexpected exception in PingWorker for address {self.address}: {e}", exc_info=True) # Add exc_info for traceback
            self.ping_failed.emit()

class AccordionWidget(QFrame):
    """Виджет-аккордеон для отображения информации о сервере игры."""
    toggled = pyqtSignal(object)

    def __init__(self, game_key, server_info, icon_path, parent=None):
        """Инициализирует AccordionWidget с ключом игры, информацией о сервере и путем к иконке.

        :param game_key: Ключ игры.
        :param server_info: Информация о сервере.
        :param icon_path: Путь к иконке игры.
        :param parent: Родительский виджет.
        """
        super().__init__(parent)
        self.game_key = game_key
        self.server_info = server_info
        self.icon_path = icon_path
        self.setStyleSheet("""QFrame { background-color: transparent; margin: 0px; }""")
        self.init_ui()

    def init_ui(self):
        """Инициализирует пользовательский интерфейс аккордеона."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.header_button = QPushButton()
        self.header_button.setCheckable(True)
        self.header_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.header_button.setMinimumHeight(80)
        self.header_button.setStyleSheet(self.button_style())
        self.header_button.clicked.connect(self.toggle)
        self.main_layout.addWidget(self.header_button)

        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(10, 10, 10, 10)
        self.header_layout.setSpacing(10)

        # Иконка игры
        self.icon_label = QLabel()
        if self.icon_path and os.path.exists(self.icon_path):
            pixmap = QPixmap(self.icon_path).scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.icon_label.setPixmap(pixmap)
        else:
            # Если путь к иконке недействителен или файл не существует, создаем прозрачный плейсхолдер
            placeholder_pixmap = QPixmap(60, 60)
            placeholder_pixmap.fill(Qt.GlobalColor.transparent) # Используйте Qt.GlobalColor.transparent
            self.icon_label.setPixmap(placeholder_pixmap)
            if not self.icon_path:
                logging.warning(f"Game icon path not provided for {self.game_key}.")
            elif not os.path.exists(self.icon_path):
                logging.warning(f"Game icon file not found at {self.icon_path} for {self.game_key}. Using placeholder.")

        self.icon_label.setFixedSize(60, 60)
        self.header_layout.addWidget(self.icon_label)

        # Вертикальный макет для имени и информации
        name_and_info_layout = QVBoxLayout()
        name_and_info_layout.setSpacing(2)

        # Имя сервера
        server_name = self.server_info.get('name', 'Unknown Server')
        self.name_label = QLabel(server_name)
        self.name_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        self.name_label.setWordWrap(True)
        name_and_info_layout.addWidget(self.name_label)

        # Горизонтальный макет для имени карты и игроков
        info_layout = QHBoxLayout()
        info_layout.setSpacing(10)

        # Имя карты
        map_name = self.server_info.get('current_map', 'N/A')
        self.map_name_label = QLabel(f"{map_name}")
        self.map_name_label.setStyleSheet("color: #cccccc; font-size: 14px;")
        info_layout.addWidget(self.map_name_label, alignment=Qt.AlignmentFlag.AlignLeft)

        # Игроки
        players = f"{self.server_info.get('num_players', '0')}/{self.server_info.get('max_players', '0')}"
        self.players_label = QLabel(f"{players}")
        self.players_label.setStyleSheet("color: #cccccc; font-size: 14px;")
        info_layout.addWidget(self.players_label, alignment=Qt.AlignmentFlag.AlignRight)

        name_and_info_layout.addLayout(info_layout)
        self.header_layout.addLayout(name_and_info_layout)

        self.header_layout.addStretch()

        # Метка пинга (без слова "Ping")
        self.ping_label = QLabel("-- ms")
        self.ping_label.setStyleSheet("color: #cccccc; font-size: 14px;")
        self.header_layout.addWidget(self.ping_label, alignment=Qt.AlignmentFlag.AlignRight)

        # Индикатор доступности (круг)
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(16, 16)
        self.status_indicator.setStyleSheet("border-radius: 8px; background-color: grey;")
        self.header_layout.addWidget(self.status_indicator, alignment=Qt.AlignmentFlag.AlignRight)

        self.header_button.setLayout(self.header_layout)

        # Область контента (иконка карты и график)
        self.content_area = QWidget()
        self.content_area.setMaximumHeight(0)
        self.content_area.setVisible(False)
        self.content_layout = QHBoxLayout()
        self.content_layout.setContentsMargins(10, 0, 10, 10)
        self.content_layout.setSpacing(10)
        self.content_area.setLayout(self.content_layout)
        self.main_layout.addWidget(self.content_area)
        self.main_layout.addStretch()

        # Иконка карты в области контента
        self.map_icon_label = QLabel()
        self.load_map_icon()
        self.map_icon_label.setFixedSize(80, 80)
        self.content_layout.addWidget(self.map_icon_label)

        # График
        self.create_graph()
        self.content_layout.addWidget(self.canvas)

        self.animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuart)
        self.animation.valueChanged.connect(self.on_animation_value_changed)
        self.animation.finished.connect(self.on_animation_finished)

        self.update_ping()

    def toggle(self):
        """Переключает видимость области контента."""
        if self.header_button.isChecked():
            self.content_area.setVisible(True)
            self.animation.setStartValue(0)
            self.animation.setEndValue(self.content_area.sizeHint().height())
            self.header_button.setStyleSheet(self.expanded_button_style())
            self.toggled.emit(self)
        else:
            self.animation.setStartValue(self.content_area.maximumHeight())
            self.animation.setEndValue(0)
            self.header_button.setStyleSheet(self.button_style())
        self.animation.start()

    def on_animation_finished(self):
        """����� ��������� �����������: ��������� ��������� � ������ �����."""
        if not self.header_button.isChecked():
            # Collapse: clamp height to zero but keep widget in layout to avoid jumpy relayouts
            self.content_area.setMaximumHeight(0)
        self.adjust_parent_size()

    def on_animation_value_changed(self, _):
        """Sync parent resizing while animation progresses to avoid jump on finish."""
        self.adjust_parent_size()

    def adjust_parent_size(self):
        """Корректирует размер родительского окна."""
        main_window = self.window()
        if main_window:
            if hasattr(main_window, 'adjust_layout_and_height'):
                main_window.adjust_layout_and_height()
            else:
                # Fallback for safety, though adjust_layout_and_height should exist
                logging.warning("MainWindow.adjust_layout_and_height not found, using adjustSize as fallback.")
                main_window.adjustSize()

    def create_graph(self):
        """Создает график для отображения данных о игроках."""
        self.figure = plt.Figure(figsize=(2, 2), dpi=100)
        self.figure.patch.set_alpha(0)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.canvas.setFixedHeight(80)
        self.canvas.setStyleSheet("background-color: transparent;")
        self.update_graph()

    def update_graph(self):
        """Обновляет график с данными о количестве игроков."""
        self.figure.clear()
        players_detailed = self.server_info.get('players_detailed', {})
        if not players_detailed:
            self.figure.clear() # Clear the figure if no data
            ax = self.figure.add_subplot(111)
            ax.set_facecolor('none')
            ax.set_title('Онлайн', color='white', fontsize=8)
            ax.tick_params(axis='both', colors='white', labelsize=8)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color('white')
            ax.spines['left'].set_color('white')
            # Optionally, display a "No data" message
            ax.text(0.5, 0.5, "Нет данных", color='white', ha='center', va='center', transform=ax.transAxes)
            self.canvas.draw()
            return

        original_times = list(players_detailed.keys())
        numerical_times = []
        valid_player_counts = []

        for time_str in original_times:
            try:
                h, m = map(int, time_str.split(':'))
                numerical_times.append(h * 60 + m)
                valid_player_counts.append(int(players_detailed[time_str]))
            except ValueError:
                logging.warning(f"Malformed time string '{time_str}' in player data for {self.game_key}")
                # Skip this data point
                continue
        
        if not numerical_times: # If all time strings were malformed
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.set_facecolor('none')
            ax.set_title('Онлайн', color='white', fontsize=8)
            ax.tick_params(axis='both', colors='white', labelsize=8)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color('white')
            ax.spines['left'].set_color('white')
            ax.text(0.5, 0.5, "Нет данных (ошибка формата времени)", color='white', ha='center', va='center', transform=ax.transAxes)
            self.canvas.draw()
            return

        self.figure.clear() # Clear before adding subplot
        ax = self.figure.add_subplot(111)
        ax.plot(numerical_times, valid_player_counts, color='green', linewidth=2)
        ax.set_facecolor('none')
        ax.grid(True, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        ax.tick_params(axis='both', colors='white', labelsize=8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        ax.tick_params(axis='x', colors='white', labelsize=6) # Keep tick styling
        ax.tick_params(axis='y', colors='white', labelsize=6)
        ax.set_title('Онлайн', color='white', fontsize=8)

        # Custom formatter for x-axis to show HH:MM
        def format_minutes_to_hhmm(minutes, pos):
            h = int(minutes // 60)
            m = int(minutes % 60)
            return f"{h:02d}:{m:02d}"

        ax.xaxis.set_major_formatter(mticker.FuncFormatter(format_minutes_to_hhmm))
        
        # Locator for x-axis ticks. MaxNLocator(3) attempts to create at most 3 ticks.
        # This might need adjustment based on the typical range of 'numerical_times'.
        ax.xaxis.set_major_locator(plt.MaxNLocator(min(3, len(numerical_times)))) # Ensure not more ticks than data points
        ax.yaxis.set_major_locator(plt.MaxNLocator(3)) # Keep y-axis locator as is

        plt.setp(ax.get_xticklabels(), rotation=45, ha='right') # Keep rotation for readability

        self.canvas.draw()

    def update_ping(self):
        """Обновляет информацию о пинге для сервера."""
        address = self.server_info.get('address')
        if address:
            self.ping_thread = QThread()
            self.ping_worker = PingWorker(address)
            self.ping_worker.moveToThread(self.ping_thread)
            self.ping_thread.started.connect(self.ping_worker.run)
            self.ping_worker.ping_result.connect(self.on_ping_result)
            self.ping_worker.ping_failed.connect(self.on_ping_failed)
            self.ping_worker.ping_result.connect(self.ping_thread.quit)
            self.ping_worker.ping_failed.connect(self.ping_thread.quit)
            self.ping_worker.ping_result.connect(self.ping_worker.deleteLater)
            self.ping_worker.ping_failed.connect(self.ping_worker.deleteLater)
            self.ping_thread.finished.connect(self.ping_thread.deleteLater)
            self.ping_thread.start()
        else:
            self.ping_label.setText("-- ms")
            self.status_indicator.setStyleSheet("border-radius: 8px; background-color: grey;")

    @pyqtSlot(int)
    def on_ping_result(self, ping_ms):
        """Обрабатывает успешный результат ping-запроса.

        :param ping_ms: Время пинга в миллисекундах.
        """
        self.ping_label.setText(f"{ping_ms} ms")
        self.status_indicator.setStyleSheet("border-radius: 8px; background-color: green;")

    @pyqtSlot()
    def on_ping_failed(self):
        """Обрабатывает неудачный результат ping-запроса."""
        self.ping_label.setText("Недоступен")
        self.status_indicator.setStyleSheet("border-radius: 8px; background-color: red;")

    def load_map_icon(self):
        """Загружает иконку карты из файла или из URL, если файл отсутствует."""
        game_name = self.game_key
        current_map = self.server_info.get('current_map', '').replace(' ', '%20')
        map_icon_filename = f"map_icons/{game_name}_{current_map}.jpg"
        default_map_icon_path = "icons/default_map.png"

        if not os.path.exists(map_icon_filename):
            try:
                icon_url = f"https://gamestates.ru/img/{game_name}/sq/{current_map}.jpg"
                icon_response = requests.get(icon_url, timeout=5) # Added timeout
                icon_response.raise_for_status() # Check for HTTP errors

                temp_pixmap = QPixmap()
                if temp_pixmap.loadFromData(icon_response.content):
                    # Содержимое является валидным изображением, сохраняем его
                    os.makedirs(os.path.dirname(map_icon_filename), exist_ok=True) # Ensure directory exists
                    with open(map_icon_filename, 'wb') as icon_file:
                        icon_file.write(icon_response.content)
                    logging.info(f"Successfully downloaded and saved map icon: {map_icon_filename}")
                else:
                    # Содержимое не является валидным изображением
                    logging.warning(f"Downloaded content for map icon {game_name} ({current_map}) is not a valid image.")
                    map_icon_filename = default_map_icon_path
            
            except requests.exceptions.RequestException as e: # More specific exception
                logging.error(f"Network error while downloading map icon for {game_name} ({current_map}): {e}")
                map_icon_filename = default_map_icon_path
            except Exception as e:
                logging.error(f"Error processing map icon for {game_name} ({current_map}): {e}")
                map_icon_filename = default_map_icon_path
        
        # Проверяем, существует ли основной или стандартный файл иконки карты
        if not os.path.exists(map_icon_filename):
            if map_icon_filename == default_map_icon_path: # Default was already tried or assigned
                 logging.warning(f"Default map icon {default_map_icon_path} not found for {game_name}.")
                 map_icon_filename = None # Иконка не найдена
            else: # Specific icon failed, now try default
                if os.path.exists(default_map_icon_path):
                    map_icon_filename = default_map_icon_path
                    logging.info(f"Using default map icon for {game_name} ({current_map}) as specific one not found.")
                else:
                    logging.warning(f"Specific map icon for {game_name} ({current_map}) not found, and default map icon {default_map_icon_path} is also missing.")
                    map_icon_filename = None


        # Загружаем иконку или плейсхолдер
        if map_icon_filename and os.path.exists(map_icon_filename):
            pixmap = QPixmap(map_icon_filename).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        else:
            pixmap = QPixmap(80, 80)
            pixmap.fill(Qt.GlobalColor.transparent) # Используйте Qt.GlobalColor.transparent
            if map_icon_filename is None: # This means default was also missing
                 logging.warning(f"No map icon available for {game_name} ({current_map}). Using transparent placeholder.")
            elif not os.path.exists(map_icon_filename): # This means default was assigned but missing
                 logging.warning(f"Assigned map icon {map_icon_filename} not found for {game_name} ({current_map}). Using transparent placeholder.")

        self.map_icon_label.setPixmap(pixmap)

    @staticmethod
    def button_style():
        """Возвращает стиль кнопки."""
        return """
            QPushButton {
                background-color: transparent;
                border: none;
                text-align: left;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(76,76,76,0.5);
            }
        """

    @staticmethod
    def expanded_button_style():
        """Возвращает стиль кнопки в развернутом состоянии."""
        return """
            QPushButton {
                background-color: transparent;
                border: none;
                text-align: left;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(76,76,76,0.5);
            }
        """

class SettingsWindow(QDialog):
    """Окно настроек приложения."""
    settings_changed = pyqtSignal()
    settings_updated = pyqtSignal(dict)
    settings_reverted = pyqtSignal()
    sync_requested = pyqtSignal()

    def __init__(self, game_list, settings, parent=None):
        """Инициализирует окно настроек.

        :param game_list: Список игр.
        :param settings: Текущие настройки.
        :param parent: Родительский виджет.
        """
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.resize(600, 400)
        self.game_list = game_list
        self.settings = copy.deepcopy(settings)  # Work on a local copy to avoid mutating external settings mid-dialog
        self.original_settings = copy.deepcopy(settings)
        self.setModal(True)  # Сделать окно настроек модальным
        self.init_ui()

    def init_ui(self):
        """Инициализирует пользовательский интерфейс окна настроек."""
        layout = QGridLayout(self)
        self.setLayout(layout)

        # Групповые блоки для лучшей организации
        games_group = QGroupBox("Игры")
        games_layout = QGridLayout()
        games_group.setLayout(games_layout)

        # Настройки отображаются в сетке
        self.game_settings = {}
        row = 0
        col = 0
        for game_key in self.game_list:
            checkbox = QCheckBox(game_key)
            # Diagnostic logging for checkbox state
            is_enabled_value = self.settings.get(game_key, {}).get('enabled', False)
            logging.debug(f"SettingsWindow.init_ui: For game '{game_key}', 'enabled' state from self.settings: {is_enabled_value}")
            checkbox.setChecked(is_enabled_value)

            spinbox = QSpinBox()
            spinbox.setMinimum(1)
            spinbox.setMaximum(3600)
            spinbox.setValue(self.settings.get(game_key, {}).get('interval', 60))

            games_layout.addWidget(checkbox, row, col)
            games_layout.addWidget(QLabel("Интервал (сек):"), row, col + 1)
            games_layout.addWidget(spinbox, row, col + 2)

            self.game_settings[game_key] = {
                'enabled': checkbox,
                'interval': spinbox
            }

            row += 1
            if row > 5:
                row = 0
                col += 3

        # Настройки прозрачности
        transparency_group = QGroupBox("Прозрачность")
        transparency_layout = QHBoxLayout()
        transparency_group.setLayout(transparency_layout)

        self.main_window_transparency = QSlider(Qt.Orientation.Horizontal)
        self.main_window_transparency.setMinimum(0)
        self.main_window_transparency.setMaximum(255)
        self.main_window_transparency.setValue(self.settings.get('main_window_transparency', 128))
        self.main_window_transparency.valueChanged.connect(self.update_transparency)

        self.main_window_transparency_label = QLabel(str(self.main_window_transparency.value()))

        transparency_layout.addWidget(QLabel("Главная форма"))
        transparency_layout.addWidget(self.main_window_transparency)
        transparency_layout.addWidget(self.main_window_transparency_label)

        # Настройки размера окна
        size_group = QGroupBox("Размер окна")
        size_layout = QHBoxLayout()
        size_group.setLayout(size_layout)

        self.window_width_spinbox = QSpinBox()
        self.window_width_spinbox.setMinimum(200)
        self.window_width_spinbox.setMaximum(2000)
        self.window_width_spinbox.setValue(self.settings.get('window_width', 600))
        self.window_width_spinbox.valueChanged.connect(self.update_window_size)

        size_layout.addWidget(QLabel("Ширина окна (пиксели):"))
        size_layout.addWidget(self.window_width_spinbox)

        layout.addWidget(games_group, 0, 0, 1, 3)
        layout.addWidget(transparency_group, 1, 0, 1, 3)
        layout.addWidget(size_group, 2, 0, 1, 3)

        button_layout = QHBoxLayout()
        sync_button = QPushButton("Обновить список из API")
        sync_button.clicked.connect(self.sync_requested.emit)

        save_button = QPushButton("Сохранить")
        save_button.clicked.connect(self.save_settings)
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(sync_button)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout, 3, 1)

    def update_transparency(self, value):
        """Обновляет уровень прозрачности основного окна.

        :param value: Уровень прозрачности (0-255).
        """
        self.main_window_transparency_label.setText(str(value))
        self.settings['main_window_transparency'] = value
        self.settings_updated.emit(copy.deepcopy(self.settings))

    def update_window_size(self, value):
        """Обновляет ширину окна.

        :param value: Ширина окна в пикселях.
        """
        self.settings['window_width'] = value
        self.settings_updated.emit(copy.deepcopy(self.settings))

    def save_settings(self):
        """Сохраняет текущие настройки и закрывает окно."""
        self.settings_changed.emit()
        self.close()

    def reject(self):
        """Отменяет изменения и восстанавливает оригинальные настройки."""
        self.settings = copy.deepcopy(self.original_settings)
        self.settings_reverted.emit()
        super().reject()

    def closeEvent(self, event):
        """?????? ????????? ?????? ? ???????? ????????? ?????????."""
        self.reject()
        event.accept()

    def get_settings(self):
        """Возвращает текущие настройки из интерфейса.

        :return: Словарь с текущими настройками.
        """
        settings = {}
        for game_key, widgets in self.game_settings.items():
            settings[game_key] = {
                'enabled': widgets['enabled'].isChecked(),
                'interval': widgets['interval'].value()
            }
        settings['main_window_transparency'] = self.main_window_transparency.value()
        settings['window_width'] = self.window_width_spinbox.value()
        return settings


    def reload(self, game_list, settings):
        """????????????????'?? ?????????? ???????? ?? ??????? ????????? ??? ???????????? ???????."""
        self.game_list = game_list
        self.settings = copy.deepcopy(settings)
        for game_key, widgets in self.game_settings.items():
            state = self.settings.get(game_key, {})
            widgets['enabled'].blockSignals(True)
            widgets['enabled'].setChecked(state.get('enabled', False))
            widgets['enabled'].blockSignals(False)

            widgets['interval'].blockSignals(True)
            widgets['interval'].setValue(state.get('interval', 60))
            widgets['interval'].blockSignals(False)

        self.main_window_transparency.blockSignals(True)
        self.main_window_transparency.setValue(self.settings.get('main_window_transparency', 128))
        self.main_window_transparency.blockSignals(False)
        self.main_window_transparency_label.setText(str(self.main_window_transparency.value()))

        self.window_width_spinbox.blockSignals(True)
        self.window_width_spinbox.setValue(self.settings.get('window_width', 600))
        self.window_width_spinbox.blockSignals(False)

class ResizeGrip(QWidget):
    """Грип для изменения размера окна."""
    def __init__(self, parent=None):
        """Инициализирует грип для изменения размера.

        :param parent: Родительский виджет.
        """
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setFixedSize(16, 16)
        self.setStyleSheet("background: transparent;")
        self.mouse_press_offset = None
        self.initial_window_geometry = None

    def paintEvent(self, event):
        """Рисует грип для изменения размера."""
        option = QStyleOptionSizeGrip()
        option.initFrom(self)
        painter = QPainter(self)
        self.style().drawControl(QStyle.ControlElement.CE_SizeGrip, option, painter, self)

    def mousePressEvent(self, event):
        """Обрабатывает нажатие мыши для начала изменения размера."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_press_offset = event.globalPosition().toPoint()
            window = self.window() # Get the top-level window
            if window:
                self.initial_window_geometry = window.geometry()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Обрабатывает перемещение мыши для изменения размера окна."""
        if event.buttons() == Qt.MouseButton.LeftButton and self.mouse_press_offset and self.initial_window_geometry:
            window_to_resize = self.window() # Get the top-level window
            if window_to_resize:
                delta = event.globalPosition().toPoint() - self.mouse_press_offset
                
                new_width = self.initial_window_geometry.width() + delta.x()
                new_height = self.initial_window_geometry.height() + delta.y()

                # Respect minimum dimensions
                new_width = max(new_width, window_to_resize.minimumWidth())
                new_height = max(new_height, window_to_resize.minimumHeight())

                # Respect maximum dimensions
                max_size = window_to_resize.maximumSize()
                # QSize.width() and QSize.height() return int, compare directly
                if new_width > max_size.width():
                    new_width = max_size.width()
                if new_height > max_size.height():
                    new_height = max_size.height()
                
                window_to_resize.resize(new_width, new_height)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Обрабатывает отпускание кнопки мыши."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_press_offset = None
            self.initial_window_geometry = None
        super().mouseReleaseEvent(event)

class MainWindow(QMainWindow):
    """Главное окно приложения."""
    def __init__(self):
        """Инициализирует главное окно приложения."""
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""QMainWindow { background-color: transparent; }""")

        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        ideal_width = int(screen_width / 5)

        try:
            with open("settings.json", "r", encoding='utf-8') as f:
                self.settings = json.load(f)
        except FileNotFoundError:
            logging.info("Settings file settings.json not found. Using default settings.")
            self.settings = {'main_window_transparency': 128, 'window_width': ideal_width}
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding settings.json: {e}. File might be corrupted. Using default settings.")
            self.settings = {'main_window_transparency': 128, 'window_width': ideal_width}
        except Exception as e:
            logging.error(f"Unexpected error loading settings: {e}. Using default settings.")
            self.settings = {'main_window_transparency': 128, 'window_width': ideal_width}

        self.resize(self.settings.get('window_width', ideal_width), 600)
        self.setMinimumWidth(ideal_width)
        self.resizing = False
        self.moving = False
        self.init_ui()
        self.load_data() # Calls adjust_layout_and_height at its end.
        self.create_tray_icon()
        self.show()
        # self.adjustSize() # Removed, load_data() will handle initial height adjustment.

    def init_ui(self):
        """Инициализирует пользовательский интерфейс главного окна."""
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("background-color: rgba(30, 30, 30, 128); border-radius: 10px;")
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(0)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(5)
        self.layout.addWidget(self.content_widget)

        # Добавляем кнопку "Добавить игры"
        self.add_games_button = QPushButton("Добавить игры")
        self.add_games_button.clicked.connect(self.open_settings)
        self.layout.addWidget(self.add_games_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.add_games_button.hide()  # Изначально скрываем кнопку

        # Грип для изменения размера окна
        self.resize_grip = ResizeGrip(self.central_widget) 
        self.resize_grip.show() # Ensure the grip is visible
        self.layout.addWidget(self.resize_grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        self.update_timers = {}

    def mousePressEvent(self, event):
        """Обрабатывает нажатие мыши на окне."""
        if event.button() == Qt.MouseButton.LeftButton:
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                self.offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self.moving = True
            else:
                self.moving = False

    def mouseMoveEvent(self, event):
        """Обрабатывает перемещение мыши для перемещения окна."""
        if self.moving:
            self.move(event.globalPosition().toPoint() - self.offset)

    def mouseReleaseEvent(self, event):
        """Обрабатывает отпускание мыши."""
        self.moving = False

    def paintEvent(self, event):
        """Рисует главное окно с заданной прозрачностью."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        transparency = self.settings.get('main_window_transparency', 128)
        painter.setBrush(QColor(30, 30, 30, transparency))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 10, 10)
        painter.end()

    def load_data(self):
        """Загружает данные о играх и обновляет интерфейс."""
        for folder in ["icons", "map_icons"]:
            if not os.path.exists(folder):
                os.makedirs(folder)

        try:
            response = requests.get("http://gamestates.ru:8000/", timeout=10)
            response.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)
            games = response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error fetching game list: {e}"
            logging.error(error_msg)
            QMessageBox.critical(self, "Ошибка сети",
                                 f"Не удалось загрузить список игр: {e}\n"
                                 "Проверьте соединение или попробуйте позже.")
            games = {}
        except json.JSONDecodeError as e:
            error_msg = f"JSON decode error fetching game list: {e}"
            logging.error(error_msg)
            QMessageBox.critical(self, "Ошибка JSON",
                                 f"Ответ списка игр поврежден: {e}\n"
                                 "Попробуйте позже или свяжитесь с администратором.")
            games = {}
        except Exception as e: # Fallback for any other unexpected errors
            error_msg = f"Unexpected error fetching game list: {e}"
            logging.error(error_msg)
            QMessageBox.critical(self, "Неожиданная ошибка",
                                 f"Произошла ошибка загрузки списка игр: {e}")
            games = {}

        # ?????? ?????? ???? ????????? ?????? - ????????? ??????
        valid_games = {}
        for game_key, server_address in games.items():
            try:
                detail_resp = requests.get(f"http://gamestates.ru:8000/{server_address}", timeout=5)
                detail_resp.raise_for_status()
                server_info = detail_resp.json()
                if not isinstance(server_info, dict) or not server_info:
                    logging.warning(f"Server {game_key} ({server_address}) returned empty/invalid details; skipping.")
                    continue
                valid_games[game_key] = {"address": server_address, "info": server_info}
            except requests.exceptions.RequestException as e:
                logging.error(f"Network error checking server {game_key} ({server_address}): {e}")
            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error for server {game_key} ({server_address}): {e}")
            except Exception as e:
                logging.error(f"Unexpected error checking server {game_key} ({server_address}): {e}")

        self.game_widgets = {}
        self.game_list = list(valid_games.keys())

        # Загрузка настроек перенесена в __init__, здесь мы только дополняем их, если нужно
        # Убедимся, что для каждой игры есть настройки по умолчанию, если они отсутствуют
        for game_key in self.game_list:
            if game_key not in self.settings:
                self.settings[game_key] = {'enabled': False, 'interval': 60}
            else:
                if 'enabled' not in self.settings[game_key]:
                    self.settings[game_key]['enabled'] = False
                if 'interval' not in self.settings[game_key]:
                    self.settings[game_key]['interval'] = 60


        # Применение настроек прозрачности
        self.apply_transparency_settings()

        # Проверяем, есть ли включенные игры
        enabled_games = [game_key for game_key in self.game_list if self.settings.get(game_key, {}).get('enabled', False)]

        if not enabled_games:
            self.add_games_button.show()
            self.content_widget.hide()
            # Ensure game_list is available for adjust_layout_and_height
            if not hasattr(self, 'game_list'): self.game_list = [] 
            self.adjust_layout_and_height() 
            return
        else:
            self.add_games_button.hide()
            self.content_widget.show()

        # Инициализируем счетчик для отслеживания количества развернутых виджетов
        expanded_count = 0
        max_expanded = 5

        for game_key, data in valid_games.items():
            if not self.settings.get(game_key, {}).get('enabled', False):
                continue
            server_address = data["address"]
            server_info = data["info"]

            ip_port = server_address.split(':')
            if len(ip_port) != 2:
                logging.error(f"Invalid server address format for {game_key}: {server_address}")
                continue
            ip, port = ip_port # Keep ip and port for logging or other potential uses

            icon_filename = f"icons/{game_key}.png"
            default_icon_path = "icons/default.png"

            if not os.path.exists(icon_filename):
                try:
                    icon_url = f"https://gamestates.ru/img/110x95/{game_key}.png"
                    icon_response = requests.get(icon_url, timeout=5) # Added timeout
                    icon_response.raise_for_status() # Check for HTTP errors
                    
                    # Проверка, что контент является изображением перед сохранением
                    temp_pixmap = QPixmap()
                    if temp_pixmap.loadFromData(icon_response.content):
                        os.makedirs(os.path.dirname(icon_filename), exist_ok=True) # Ensure directory exists
                        with open(icon_filename, 'wb') as icon_file:
                            icon_file.write(icon_response.content)
                        logging.info(f"Successfully downloaded and saved game icon: {icon_filename}")
                    else:
                        logging.warning(f"Downloaded content for game icon {game_key} is not a valid image. Using default.")
                        icon_filename = default_icon_path
                        
                except requests.exceptions.RequestException as e: # More specific exception
                    logging.error(f"Network error while downloading game icon for {game_key}: {e}")
                    icon_filename = default_icon_path
                except Exception as e:
                    logging.error(f"Error processing game icon for {game_key}: {e}")
                    icon_filename = default_icon_path

            # Если основной файл иконки не существует, проверяем стандартную иконку
            if not os.path.exists(icon_filename):
                if os.path.exists(default_icon_path): # Check if specific icon failed and default exists
                    icon_filename = default_icon_path
                    logging.info(f"Game icon for {game_key} not found or failed to download. Using default icon: {default_icon_path}")
                else: # Specific icon failed AND default is also missing
                    logging.warning(f"Game icon for {game_key} not found, and default icon {default_icon_path} is also missing. Using None for icon path.")
                    icon_filename = None # Иконка не найдена

            server_widget = AccordionWidget(game_key, server_info, icon_filename, parent=self.content_widget)
            server_widget.toggled.connect(self.accordion_toggled)
            self.content_layout.addWidget(server_widget)
            self.game_widgets[game_key] = server_widget

            interval = self.settings.get(game_key, {}).get('interval', 60) * 1000
            timer = QTimer(self)
            # Pass the full server_address to update_server_data
            timer.timeout.connect(lambda gk=game_key, sa=server_address: self.update_server_data(gk, sa))
            timer.start(interval)
            self.update_timers[game_key] = timer

            # Разворачиваем первые 5 виджетов по умолчанию
            if expanded_count < max_expanded:
                server_widget.header_button.setChecked(True)
                expanded_count += 1

        self.content_layout.addStretch()
        self.adjust_layout_and_height()

    def apply_transparency_settings(self):
        """Применяет настройки прозрачности к центральному виджету."""
        transparency = self.settings.get('main_window_transparency', 128)
        self.central_widget.setStyleSheet(f"background-color: rgba(30, 30, 30, {transparency}); border-radius: 10px;")

    def accordion_toggled(self, toggled_widget):
        """Обрабатывает событие переключения аккордеона.

        :param toggled_widget: Переключенный виджет.
        """
        for widget in self.game_widgets.values():
            if widget != toggled_widget and widget.header_button.isChecked():
                widget.header_button.setChecked(False)
                widget.toggle() 
        # self.adjust_layout_and_height() # REMOVED / COMMENTED OUT
        logging.debug("MainWindow.accordion_toggled: Relying on individual accordion animation.finished to adjust height.")

    def update_server_data(self, game_key, server_address): # Changed 'ip' to 'server_address'
        """Обновляет данные о сервере и обновляет соответствующий виджет.

        :param game_key: Ключ игры.
        :param server_address: Полный адрес сервера (IP:Port).
        """
        try:
            # Use the full server_address (IP:Port) for fetching server details
            server_response = requests.get(f"http://gamestates.ru:8000/{server_address}", timeout=5)
            server_response.raise_for_status()
            server_info = server_response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error updating server data for {game_key} ({server_address}): {e}")
            return
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error updating server data for {game_key} ({server_address}): {e}")
            return
        except Exception as e:
            logging.error(f"Unexpected error updating server data for {game_key} ({server_address}): {e}")
            return

        widget = self.game_widgets.get(game_key)
        if widget:
            widget.server_info = server_info
            widget.name_label.setText(server_info.get('name', 'Unknown Server'))
            players = f"{server_info.get('num_players', '0')}/{server_info.get('max_players', '0')}"
            widget.players_label.setText(f"{players}")
            map_name = server_info.get('current_map', 'N/A')
            widget.map_name_label.setText(f"{map_name}")
            widget.update_graph()
            widget.update_ping()
            widget.load_map_icon()


    def sync_game_list_from_api(self):
        """???????? ?????? ?? API ? ????????? ????????? ? ?????????."""
        self.reload_data()
        if hasattr(self, 'settings_window'):
            try:
                self.settings_window.reload(self.game_list, self.settings)
            except Exception as e:
                logging.error(f"Failed to reload settings window after sync: {e}")

    def create_tray_icon(self):
        """Создает иконку в трее и меню."""
        self.tray_icon = QSystemTrayIcon(self)
        if os.path.exists("icons/tray_icon.png"):
            self.tray_icon.setIcon(QIcon("icons/tray_icon.png"))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        show_action = QAction("Показать", self)
        hide_action = QAction("Скрыть", self)
        settings_action = QAction("Настройки", self)
        quit_action = QAction("Выход", self)

        # Подключаем действие выхода
        quit_action.triggered.connect(self.exit_app)

        show_action.triggered.connect(self.show_window)
        hide_action.triggered.connect(self.hide_window)
        settings_action.triggered.connect(self.open_settings)

        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addSeparator()
        tray_menu.addAction(settings_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        """Обрабатывает активацию иконки в трее.

        :param reason: Причина активации.
        """
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def show_window(self):
        """Показывает главное окно."""
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_window(self):
        """Скрывает главное окно."""
        self.hide()

    def exit_app(self):
        """?????????? ????? ?? ?????????? ? ????????? ?????? ?? ????."""
        # ????????????? ??? ???????
        for timer in self.update_timers.values():
            timer.stop()

        # ????????? ??????, ???? ??? ????
        for widget in self.game_widgets.values():
            thread = getattr(widget, 'ping_thread', None)
            if not thread:
                continue
            try:
                if thread.isRunning():
                    thread.quit()
                    thread.wait()
            except RuntimeError:
                # Thread object already deleted; nothing to stop
                pass

        # ??????? ?????? ?? ????
        self.tray_icon.hide()
        self.tray_icon.deleteLater()

        # ????????? ????????? ??????????
        QApplication.instance().quit()

    def closeEvent(self, event):
        """Обрабатывает событие закрытия окна приложения."""
        event.ignore()
        self.hide()

    def open_settings(self):
        """Открывает окно настроек."""
        # Предотвращаем открытие нескольких окон настроек
        if hasattr(self, 'settings_window') and self.settings_window.isVisible():
            try:
                self.settings_window.reload(self.game_list, self.settings)
            except Exception as e:
                logging.error(f"Failed to reload settings window before showing: {e}")
            self.settings_window.raise_()
            self.settings_window.activateWindow()
            return
        self.original_settings = copy.deepcopy(self.settings)
        self.settings_window = SettingsWindow(self.game_list, self.settings)
        self.settings_window.settings_changed.connect(self.apply_settings)
        self.settings_window.settings_updated.connect(self.apply_temporary_settings)
        self.settings_window.settings_reverted.connect(self.restore_original_settings)
        self.settings_window.sync_requested.connect(self.sync_game_list_from_api)
        self.settings_window.exec()

    def apply_settings(self):
        """Применяет новые настройки и сохраняет их в файл."""
        new_settings = self.settings_window.get_settings()
        self.settings.update(new_settings)
        try:
            with open("settings.json", "w", encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
            logging.info("Settings saved successfully.")
        except IOError as e:
            logging.error(f"IOError saving settings to settings.json: {e}")
        except Exception as e:
            logging.error(f"Unexpected error saving settings: {e}")

        new_width = self.settings.get('window_width', self.width())
        # Preserve current height before reload_data, which will then adjust height properly
        self.resize(new_width, self.height())
        
        self.reload_data() # This eventually calls load_data(), which calls adjust_layout_and_height()
        self.adjust_layout_and_height() # Add this explicit call
        logging.debug("Called adjust_layout_and_height explicitly after reload_data in apply_settings.")

    def apply_temporary_settings(self, settings):
        """Применяет временные настройки.

        :param settings: Словарь с временными настройками.
        """
        self.settings.update(settings)
        self.apply_transparency_settings()
        self.resize(self.settings.get('window_width', self.width()), self.height())

    def restore_original_settings(self):
        """Восстанавливает оригинальные настройки."""
        self.settings = copy.deepcopy(self.original_settings)
        self.apply_transparency_settings()
        self.resize(self.settings.get('window_width', self.width()), self.height())

    def reload_data(self):
        """Перезагружает данные о серверах и обновляет интерфейс."""
        for widget in self.game_widgets.values():
            widget.setParent(None)
        for timer in self.update_timers.values():
            timer.stop()
        self.game_widgets.clear()
        self.update_timers.clear()
        self.load_data()

    def resizeEvent(self, event):
        """Обрабатывает изменение размера окна."""
        # This event is called when the window is resized by any means,
        # including programmatically or by user dragging the ResizeGrip.
        # We generally don't need to call adjust_layout_and_height here
        # as it might create loops if not handled carefully.
        # The height adjustment should be triggered by specific content changes.
        super().resizeEvent(event)

    def adjust_layout_and_height(self):
        """Adjusts the window height to fit content, preserving current width."""
        current_width = self.width()
        
        # Force layout to recalculate its hint based on current content and width
        self.layout.invalidate()
        self.layout.activate()

        ideal_height = self.layout.sizeHint().height()
        
        # Determine minimum sensible height based on whether games are displayed
        min_height_for_no_games = 100  # Enough for "Add Games" button, margins, and grip
        min_height_for_games = 150     # Enough for at least one collapsed accordion, button, grip etc.

        has_enabled_games = False
        # Ensure game_list and settings attributes exist before checking
        if hasattr(self, 'game_list') and self.game_list and \
           hasattr(self, 'settings') and self.settings: # Check settings attribute
            for game_key in self.game_list:
                # Ensure game_key exists in settings to prevent KeyError
                if game_key in self.settings and self.settings[game_key].get('enabled', False):
                    has_enabled_games = True
                    break
        
        if has_enabled_games:
            ideal_height = max(ideal_height, min_height_for_games)
        else:
            ideal_height = max(ideal_height, min_height_for_no_games)

        # Respect window's own explicitly set minimumHeight if it's larger
        ideal_height = max(ideal_height, self.minimumHeight())
        # Respect window's own explicitly set maximumHeight
        ideal_height = min(ideal_height, self.maximumHeight())
        
        if self.height() != ideal_height or self.width() != current_width: # Check width too just in case
            self.resize(current_width, ideal_height)
            
        logging.debug(f"Adjusted window size: W={current_width}, H={ideal_height}. Layout ideal H: {self.layout.sizeHint().height()}")


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, # Changed to DEBUG
        format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s',
        filename='app.log',
        filemode='a'  # Append to the log file on each run
    )
    # Example of adding a console handler for more immediate feedback on errors
    # console_handler = logging.StreamHandler()
    # console_handler.setLevel(logging.ERROR) # Only show errors on console
    # formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    # console_handler.setFormatter(formatter)
    # logging.getLogger().addHandler(console_handler)

    logging.info("Application starting.")
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = MainWindow()
    window.show()
    logging.info("Application started and main window shown.")
    exit_code = app.exec()
    logging.info(f"Application exiting with code {exit_code}.")
    sys.exit(exit_code)
