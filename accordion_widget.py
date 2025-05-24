import os
import logging
import requests
from PyQt6.QtWidgets import (
    QFrame, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, 
    QWidget, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QColor # QColor for Qt.GlobalColor.transparent
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QThread, 
    QObject, pyqtSlot # QObject is parent of PingWorker. QThread, pyqtSlot for ping mechanism.
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# Assuming ping_worker.py is in the same directory or accessible in PYTHONPATH
from ping_worker import PingWorker 

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
            placeholder_pixmap.fill(Qt.GlobalColor.transparent) 
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
        self.animation.finished.connect(self.adjust_parent_size)

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
            self.ping_worker = PingWorker(address) # PingWorker is imported
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
        default_map_icon_path = "icons/default_map.png" # Path relative to where app.py runs

        # Ensure the map_icons directory exists
        os.makedirs("map_icons", exist_ok=True)


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
