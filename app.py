import sys
import os
import requests
import json
import copy
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QMainWindow,
    QSystemTrayIcon, QMenu, QDialog, QCheckBox, QSpinBox, QStyle, QSizePolicy,
    QSlider, QGridLayout, QGroupBox, QStyleOptionSizeGrip
)
from PyQt6.QtGui import QIcon, QPixmap, QAction, QCursor, QPainter, QColor
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QTimer, QThread, QObject, pyqtSlot, QSize, QPoint
)
from ping3 import ping
from ping3.errors import PingError
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

class PingWorker(QObject):
    ping_result = pyqtSignal(int)
    ping_failed = pyqtSignal()

    def __init__(self, address):
        super().__init__()
        self.address = address

    def run(self):
        try:
            response = ping(self.address, timeout=2)
            if response:
                self.ping_result.emit(int(response * 1000))
            else:
                self.ping_failed.emit()
        except PingError:
            self.ping_failed.emit()

class AccordionWidget(QFrame):
    toggled = pyqtSignal(object)

    def __init__(self, game_key, server_info, icon_path, parent=None):
        super().__init__(parent)
        self.game_key = game_key
        self.server_info = server_info
        self.icon_path = icon_path
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                margin: 0px; /* Removed margin to prevent extra spacing */
            }
        """)
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.header_button = QPushButton()
        self.header_button.setCheckable(True)
        self.header_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.header_button.setMinimumHeight(80)  # Increased height to accommodate fonts
        self.header_button.setStyleSheet(self.button_style())
        self.header_button.clicked.connect(self.toggle)
        self.main_layout.addWidget(self.header_button)

        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(10, 10, 10, 10)
        self.header_layout.setSpacing(10)

        # Game Icon
        self.icon_label = QLabel()
        pixmap = QPixmap(self.icon_path).scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.icon_label.setPixmap(pixmap)
        self.icon_label.setFixedSize(60, 60)  # Ensuring icon fits into a square
        self.header_layout.addWidget(self.icon_label)

        # Vertical Layout for Name and Info
        name_and_info_layout = QVBoxLayout()
        name_and_info_layout.setSpacing(2)

        # Game Name
        server_name = self.server_info.get('name', 'Unknown Server')
        self.name_label = QLabel(server_name)
        self.name_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        self.name_label.setWordWrap(True)
        name_and_info_layout.addWidget(self.name_label)

        # Horizontal Layout for Map Name and Players
        info_layout = QHBoxLayout()
        info_layout.setSpacing(10)

        # Map Name
        map_name = self.server_info.get('current_map', 'N/A')
        self.map_name_label = QLabel(f"{map_name}")
        self.map_name_label.setStyleSheet("color: #cccccc; font-size: 14px;")
        info_layout.addWidget(self.map_name_label, alignment=Qt.AlignmentFlag.AlignLeft)

        # Players
        players = f"{self.server_info.get('num_players', '0')}/{self.server_info.get('max_players', '0')}"
        self.players_label = QLabel(f"{players}")
        self.players_label.setStyleSheet("color: #cccccc; font-size: 14px;")
        info_layout.addWidget(self.players_label, alignment=Qt.AlignmentFlag.AlignRight)

        name_and_info_layout.addLayout(info_layout)
        self.header_layout.addLayout(name_and_info_layout)

        self.header_layout.addStretch()

        # Ping Label (without the word "Ping")
        self.ping_label = QLabel("-- ms")
        self.ping_label.setStyleSheet("color: #cccccc; font-size: 14px;")
        self.header_layout.addWidget(self.ping_label, alignment=Qt.AlignmentFlag.AlignRight)

        # Availability Indicator (Circle)
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(16, 16)
        self.status_indicator.setStyleSheet("border-radius: 8px; background-color: grey;")
        self.header_layout.addWidget(self.status_indicator, alignment=Qt.AlignmentFlag.AlignRight)

        self.header_button.setLayout(self.header_layout)

        # Content Area (Map Icon and Graph)
        self.content_area = QWidget()
        self.content_area.setMaximumHeight(0)
        self.content_area.setVisible(False)
        self.content_layout = QHBoxLayout()  # Changed to QHBoxLayout for side-by-side
        self.content_layout.setContentsMargins(10, 0, 10, 10)
        self.content_layout.setSpacing(10)
        self.content_area.setLayout(self.content_layout)
        self.main_layout.addWidget(self.content_area)
        self.main_layout.addStretch()  # Added stretch to push content upwards

        # Map Icon in Content Area
        self.map_icon_label = QLabel()
        self.load_map_icon()
        self.map_icon_label.setFixedSize(80, 80)
        self.content_layout.addWidget(self.map_icon_label)

        # Graph
        self.create_graph()
        self.content_layout.addWidget(self.canvas)

        self.animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuart)

        self.update_ping()

    def toggle(self):
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
        main_window = self.window()
        if main_window:
            main_window.adjustSize()

    def create_graph(self):
        self.figure = plt.Figure(figsize=(2, 2), dpi=100)
        self.figure.patch.set_alpha(0)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.canvas.setFixedHeight(80)
        self.canvas.setStyleSheet("background-color: transparent;")
        self.update_graph()

    def update_graph(self):
        self.figure.clear()
        players_detailed = self.server_info.get('players_detailed', {})
        if not players_detailed:
            return
        times = list(players_detailed.keys())
        player_counts = [int(players_detailed[time]) for time in times]

        ax = self.figure.add_subplot(111)
        ax.plot(times, player_counts, color='green', linewidth=2)
        ax.set_facecolor('none')
        ax.grid(True, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        ax.tick_params(axis='both', colors='white', labelsize=8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        ax.tick_params(axis='x', colors='white', labelsize=6)
        ax.tick_params(axis='y', colors='white', labelsize=6)
        ax.set_title('Онлайн', color='white', fontsize=8)
        ax.xaxis.set_major_locator(plt.MaxNLocator(3))
        ax.yaxis.set_major_locator(plt.MaxNLocator(3))
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

        self.canvas.draw()

    def update_ping(self):
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
        self.ping_label.setText(f"{ping_ms} ms")
        self.status_indicator.setStyleSheet("border-radius: 8px; background-color: green;")

    @pyqtSlot()
    def on_ping_failed(self):
        self.ping_label.setText("Недоступен")
        self.status_indicator.setStyleSheet("border-radius: 8px; background-color: red;")

    def load_map_icon(self):
        game_name = self.game_key
        current_map = self.server_info.get('current_map', '').replace(' ', '%20')
        map_icon_filename = f"map_icons/{game_name}_{current_map}.jpg"
        
        if not os.path.exists(map_icon_filename):
            try:
                icon_url = f"https://gamestates.ru/img/{game_name}/sq/{current_map}.jpg"
                icon_response = requests.get(icon_url)
                
                # Проверяем, является ли содержимое изображением
                if "image" in icon_response.headers.get("Content-Type", ""):
                    # Если содержимое является изображением, сохраняем его
                    with open(map_icon_filename, 'wb') as icon_file:
                        icon_file.write(icon_response.content)
                else:
                    # Если это не изображение, загружаем иконку по умолчанию
                    print(f"Не удалось загрузить изображение карты для {game_name}. Загружен HTML-файл.")
                    map_icon_filename = "icons/default_map.png"
            
            except Exception as e:
                print(f"Ошибка при загрузке иконки карты для {game_name}: {e}")
                map_icon_filename = "icons/default_map.png"
        
        # Если файл всё ещё не существует, используем иконку по умолчанию
        if not os.path.exists(map_icon_filename):
            map_icon_filename = "icons/default_map.png"

        # Загружаем иконку
        pixmap = QPixmap(map_icon_filename).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.map_icon_label.setPixmap(pixmap)


    @staticmethod
    def button_style():
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
    settings_changed = pyqtSignal()
    settings_updated = pyqtSignal(dict)
    settings_reverted = pyqtSignal()

    def __init__(self, game_list, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.resize(600, 400)
        self.game_list = game_list
        self.settings = settings
        self.original_settings = copy.deepcopy(settings)
        self.setModal(True)  # Make the settings window modal
        self.init_ui()

    def init_ui(self):
        layout = QGridLayout(self)
        self.setLayout(layout)

        # Group boxes for better organization
        games_group = QGroupBox("Игры")
        games_layout = QGridLayout()
        games_group.setLayout(games_layout)

        # Adjusted to display settings in a grid
        self.game_settings = {}
        row = 0
        col = 0
        for game_key in self.game_list:
            checkbox = QCheckBox(game_key)
            checkbox.setChecked(self.settings.get(game_key, {}).get('enabled', False))  # Изменено на False

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

        # Transparency settings
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

        # Window size settings
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
        save_button = QPushButton("Сохранить")
        save_button.clicked.connect(self.save_settings)
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout, 3, 1)

    def update_transparency(self, value):
        self.main_window_transparency_label.setText(str(value))
        self.settings['main_window_transparency'] = value
        self.settings_updated.emit(self.settings)

    def update_window_size(self, value):
        self.settings['window_width'] = value
        self.settings_updated.emit(self.settings)

    def save_settings(self):
        self.settings_changed.emit()
        self.close()

    def reject(self):
        # Restore original settings
        self.settings = copy.deepcopy(self.original_settings)
        self.settings_reverted.emit()
        super().reject()

    def get_settings(self):
        settings = {}
        for game_key, widgets in self.game_settings.items():
            settings[game_key] = {
                'enabled': widgets['enabled'].isChecked(),
                'interval': widgets['interval'].value()
            }
        settings['main_window_transparency'] = self.main_window_transparency.value()
        settings['window_width'] = self.window_width_spinbox.value()
        return settings

class ResizeGrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setFixedSize(16, 16)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        option = QStyleOptionSizeGrip()
        option.initFrom(self)
        painter = QPainter(self)
        self.style().drawControl(QStyle.ControlElement.CE_SizeGrip, option, painter, self)

    def mousePressEvent(self, event):
        self.offset = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = event.globalPosition().toPoint() - self.offset
        self.offset = event.globalPosition().toPoint()
        parent = self.parent()
        new_width = parent.width() + delta.x()
        parent.resize(new_width, parent.height())
        parent.adjustSize()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""
            QMainWindow {
                background-color: transparent;
            }
        """)

        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        ideal_width = int(screen_width / 5)

        if os.path.exists("settings.json"):
            try:
                with open("settings.json", "r", encoding='utf-8') as f:
                    self.settings = json.load(f)
            except Exception as e:
                print(f"Ошибка при загрузке настроек: {e}")
                self.settings = {}
        else:
            self.settings = {}

        self.resize(self.settings.get('window_width', ideal_width), 600)
        self.setMinimumWidth(ideal_width)  # Set minimum width
        self.resizing = False
        self.moving = False
        self.init_ui()
        self.load_data()
        self.create_tray_icon()
        self.show()
        self.adjustSize()  # Ensure correct size upon startup

    def init_ui(self):
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("background-color: rgba(30, 30, 30, 128); border-radius: 10px;")  # Semi-transparent background
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(0)  # Set spacing to 0 to prevent extra space

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(5)  # Minimal spacing between accordions
        self.layout.addWidget(self.content_widget)

        # Добавляем кнопку "Добавить игры"
        self.add_games_button = QPushButton("Добавить игры")
        self.add_games_button.clicked.connect(self.open_settings)
        self.layout.addWidget(self.add_games_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.add_games_button.hide()  # Изначально скрываем кнопку

        # Resize Grip
        # self.resize_grip = ResizeGrip(self)
        # self.resize_grip.hide()  # Initially hidden
        # self.layout.addWidget(self.resize_grip, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        self.update_timers = {}

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                self.offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self.moving = True
            else:
                self.moving = False

    def mouseMoveEvent(self, event):
        if self.moving:
            self.move(event.globalPosition().toPoint() - self.offset)

    def mouseReleaseEvent(self, event):
        self.moving = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        rect.setWidth(rect.width())
        rect.setHeight(rect.height())
        transparency = self.settings.get('main_window_transparency', 128)
        painter.setBrush(QColor(30, 30, 30, transparency))  # Use transparency from settings
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 10, 10)
        painter.end()

    def load_data(self):
        for folder in ["icons", "map_icons"]:
            if not os.path.exists(folder):
                os.makedirs(folder)

        try:
            response = requests.get("http://gamestates.ru:8000/")
            response.raise_for_status()
            games = response.json()
        except Exception as e:
            print(f"Ошибка при получении списка игр: {e}")
            games = {}

        self.game_widgets = {}
        self.game_list = list(games.keys())

        if os.path.exists("settings.json"):
            try:
                with open("settings.json", "r", encoding='utf-8') as f:
                    self.settings = json.load(f)
            except Exception as e:
                print(f"Ошибка при загрузке настроек: {e}")
                self.settings = {game_key: {'enabled': False, 'interval': 60} for game_key in self.game_list}
        else:
            self.settings = {game_key: {'enabled': False, 'interval': 60} for game_key in self.game_list}  # Изменено на False

        # Apply transparency settings
        self.apply_transparency_settings()

        # Проверяем, есть ли включенные игры
        enabled_games = [game_key for game_key in self.game_list if self.settings.get(game_key, {}).get('enabled', False)]

        if not enabled_games:
            self.add_games_button.show()
            self.content_widget.hide()
            self.adjustSize()  # Подгоняем размер окна
            return
        else:
            self.add_games_button.hide()
            self.content_widget.show()

        # Initialize a counter to track the number of expanded widgets
        expanded_count = 0
        max_expanded = 5  # Number of widgets to expand by default

        for game_key, server_address in games.items():
            if not self.settings.get(game_key, {}).get('enabled', False):
                continue

            ip_port = server_address.split(':')
            if len(ip_port) != 2:
                print(f"Неверный формат адреса сервера для {game_key}: {server_address}")
                continue
            ip, port = ip_port

            try:
                server_response = requests.get(f"http://gamestates.ru:8000/{ip}")
                server_response.raise_for_status()
                server_info = server_response.json()
            except Exception as e:
                print(f"Ошибка при получении данных сервера {game_key}: {e}")
                continue

            icon_filename = f"icons/{game_key}.png"
            if not os.path.exists(icon_filename):
                try:
                    icon_url = f"https://gamestates.ru/img/110x95/{game_key}.png"
                    icon_response = requests.get(icon_url)
                    if icon_response.status_code == 200:
                        with open(icon_filename, 'wb') as icon_file:
                            icon_file.write(icon_response.content)
                    else:
                        print(f"Не удалось скачать иконку для {game_key}: статус {icon_response.status_code}")
                        icon_filename = "icons/default.png"
                except Exception as e:
                    print(f"Ошибка при скачивании иконки для {game_key}: {e}")
                    icon_filename = "icons/default.png"

            if not os.path.exists(icon_filename):
                icon_filename = "icons/default.png"

            server_widget = AccordionWidget(game_key, server_info, icon_filename, parent=self.content_widget)
            server_widget.toggled.connect(self.accordion_toggled)
            self.content_layout.addWidget(server_widget)
            self.game_widgets[game_key] = server_widget

            interval = self.settings.get(game_key, {}).get('interval', 60) * 1000
            timer = QTimer(self)
            timer.timeout.connect(lambda gk=game_key, ip=ip: self.update_server_data(gk, ip))
            timer.start(interval)
            self.update_timers[game_key] = timer

            # Expand the first 5 widgets by default
            if expanded_count < max_expanded:
                server_widget.header_button.setChecked(True)
                # server_widget.toggle()
                expanded_count += 1

        self.content_layout.addStretch()
        self.adjustSize()  # Подгоняем размер окна

    def apply_transparency_settings(self):
        transparency = self.settings.get('main_window_transparency', 128)
        self.central_widget.setStyleSheet(f"background-color: rgba(30, 30, 30, {transparency}); border-radius: 10px;")

    def accordion_toggled(self, toggled_widget):
        for widget in self.game_widgets.values():
            if widget != toggled_widget and widget.header_button.isChecked():
                widget.header_button.setChecked(False)
                widget.toggle()
        self.adjustSize()

    def update_server_data(self, game_key, ip):
        try:
            server_response = requests.get(f"http://gamestates.ru:8000/{ip}")
            server_response.raise_for_status()
            server_info = server_response.json()
        except Exception as e:
            print(f"Ошибка при обновлении данных сервера {game_key}: {e}")
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

    def create_tray_icon(self):
        """Создание иконки в трее и меню"""
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
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_window(self):
        self.hide()

    def exit_app(self):
        """Корректный выход из приложения с удалением иконки из трея"""
        # Останавливаем все таймеры
        for timer in self.update_timers.values():
            timer.stop()

        # Завершаем потоки, если они есть
        for widget in self.game_widgets.values():
            if hasattr(widget, 'ping_thread') and widget.ping_thread.isRunning():
                widget.ping_thread.quit()
                widget.ping_thread.wait()  # Ожидание завершения потока

        # Удаляем иконку из трея
        self.tray_icon.hide()
        self.tray_icon.deleteLater()  # Убираем иконку из трея окончательно

        # Корректно закрываем приложение
        QApplication.instance().quit()


    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def open_settings(self):
        # Prevent multiple settings windows
        if hasattr(self, 'settings_window') and self.settings_window.isVisible():
            self.settings_window.raise_()
            self.settings_window.activateWindow()
            return
        self.original_settings = copy.deepcopy(self.settings)
        self.settings_window = SettingsWindow(self.game_list, self.settings)
        self.settings_window.settings_changed.connect(self.apply_settings)
        self.settings_window.settings_updated.connect(self.apply_temporary_settings)
        self.settings_window.settings_reverted.connect(self.restore_original_settings)
        self.settings_window.exec()

    def apply_settings(self):
        new_settings = self.settings_window.get_settings()
        self.settings.update(new_settings)
        try:
            with open("settings.json", "w", encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка при сохранении настроек: {e}")

        self.reload_data()

    def apply_temporary_settings(self, settings):
        self.settings.update(settings)
        self.apply_transparency_settings()
        self.resize(self.settings.get('window_width', self.width()), self.height())

    def restore_original_settings(self):
        self.settings = copy.deepcopy(self.original_settings)
        self.apply_transparency_settings()
        self.resize(self.settings.get('window_width', self.width()), self.height())

    def reload_data(self):
        for widget in self.game_widgets.values():
            widget.setParent(None)
        for timer in self.update_timers.values():
            timer.stop()
        self.game_widgets.clear()
        self.update_timers.clear()
        self.load_data()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # if self.resize_enabled:
        #     self.resize_grip.move(self.width() - self.resize_grip.width(), self.height() - self.resize_grip.height())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
