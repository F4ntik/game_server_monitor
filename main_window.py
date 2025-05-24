import sys 
import os
import logging
import requests
import json
import copy

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QMainWindow, QSystemTrayIcon, QMenu, QMessageBox, QStyle, QStyleOptionSizeGrip
)
from PyQt6.QtGui import QIcon, QPixmap, QAction, QPainter, QColor, QCursor
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal, QSize

# Imports for the previously refactored classes
from accordion_widget import AccordionWidget 
from settings_window import SettingsWindow
from resize_grip import ResizeGrip
# PingWorker is used by AccordionWidget, so it's not directly imported here.

class MainWindow(QMainWindow):
    """Главное окно приложения."""
    def __init__(self):
        """Инициализирует главное окно приложения."""
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""QMainWindow { background-color: transparent; }""")

        screen = QApplication.primaryScreen()
        if screen: 
            screen_geometry = screen.availableGeometry()
            screen_width = screen_geometry.width()
            ideal_width = int(screen_width / 5)
        else: 
            ideal_width = 600 
            logging.warning("No primary screen found, using default ideal_width=600.")


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
            logging.error(f"Unexpected error loading settings: {e}", exc_info=True)
            self.settings = {'main_window_transparency': 128, 'window_width': ideal_width}

        self.resize(self.settings.get('window_width', ideal_width), 600) 
        self.setMinimumWidth(ideal_width) 
        
        self.resizing = False
        self.moving = False
        self.height_adjustment_pending = False 
        self.init_ui() # Call before load_data as init_ui sets up content_layout
        self.load_data() 
        self.create_tray_icon()
        # self.show() # Show is called from app.py after instantiation

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

        self.add_games_button = QPushButton("Добавить игры")
        self.add_games_button.clicked.connect(self.open_settings)
        self.layout.addWidget(self.add_games_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.add_games_button.hide()

        self.resize_grip = ResizeGrip(self.central_widget) 
        self.layout.addWidget(self.resize_grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        
        self.update_timers = {}
        self.game_widgets = {} 

    def mousePressEvent(self, event):
        """Обрабатывает нажатие мыши на окне."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.resize_grip.geometry().contains(event.pos()): 
                 self.moving = False 
            elif event.modifiers() == Qt.KeyboardModifier.ShiftModifier: 
                self.offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self.moving = True
            else:
                self.offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self.moving = True 
        super().mousePressEvent(event)


    def mouseMoveEvent(self, event):
        """Обрабатывает перемещение мыши для перемещения окна."""
        if self.moving:
            self.move(event.globalPosition().toPoint() - self.offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Обрабатывает отпускание мыши."""
        self.moving = False
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        """Рисует главное окно с заданной прозрачностью."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        transparency = self.settings.get('main_window_transparency', 128)
        painter.setBrush(QColor(30, 30, 30, transparency))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 10, 10)

    def load_data(self):
        """Загружает данные о играх и обновляет интерфейс."""
        for folder in ["icons", "map_icons"]:
            if not os.path.exists(folder):
                os.makedirs(folder)

        try:
            response = requests.get("http://gamestates.ru:8000/", timeout=10)
            response.raise_for_status() 
            games = response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error fetching game list: {e}"
            logging.error(error_msg)
            QMessageBox.critical(self, "Ошибка сети",
                                 f"Не удалось получить список игр с сервера: {e}\n"
                                 "Проверьте ваше интернет-соединение или попробуйте позже.")
            games = {}
        except json.JSONDecodeError as e:
            error_msg = f"JSON decode error fetching game list: {e}"
            logging.error(error_msg)
            QMessageBox.critical(self, "Ошибка данных",
                                 f"Получен неверный формат данных для списка игр: {e}\n"
                                 "Приложение может работать некорректно.")
            games = {}
        except Exception as e: 
            error_msg = f"Unexpected error fetching game list: {e}"
            logging.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "Неизвестная ошибка",
                                 f"Произошла непредвиденная ошибка: {e}")
            games = {}

        # Clear previous widgets before loading new ones
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        self.game_widgets.clear() 
        self.game_list = list(games.keys()) 


        for game_key in self.game_list: 
            if game_key not in self.settings:
                self.settings[game_key] = {'enabled': False, 'interval': 60}
            else:
                if 'enabled' not in self.settings[game_key]:
                    self.settings[game_key]['enabled'] = False
                if 'interval' not in self.settings[game_key]:
                    self.settings[game_key]['interval'] = 60
        
        self.apply_transparency_settings()

        enabled_games_count = 0
        for game_key in self.game_list: 
            if self.settings.get(game_key, {}).get('enabled', False):
                enabled_games_count +=1
        
        if enabled_games_count == 0:
            self.add_games_button.show()
            self.content_widget.hide()
            self.adjust_layout_and_height() 
            return
        else:
            self.add_games_button.hide()
            self.content_widget.show()

        expanded_count = 0
        max_expanded = 5

        for game_key, server_address in games.items():
            if not self.settings.get(game_key, {}).get('enabled', False):
                continue

            ip_port = server_address.split(':')
            if len(ip_port) != 2:
                logging.error(f"Invalid server address format for {game_key}: {server_address}")
                continue

            try:
                server_response = requests.get(f"http://gamestates.ru:8000/{server_address}", timeout=5)
                server_response.raise_for_status()
                server_info = server_response.json()
            except requests.exceptions.RequestException as e:
                logging.error(f"Network error fetching server data for {game_key} ({server_address}): {e}")
                continue
            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error for server {game_key} ({server_address}): {e}")
                continue
            except Exception as e:
                logging.error(f"Unexpected error fetching server data for {game_key} ({server_address}): {e}", exc_info=True)
                continue

            icon_filename = f"icons/{game_key}.png"
            default_icon_path = "icons/default.png"

            if not os.path.exists(icon_filename):
                try:
                    icon_url = f"https://gamestates.ru/img/110x95/{game_key}.png"
                    icon_response = requests.get(icon_url, timeout=5) 
                    icon_response.raise_for_status() 
                    
                    temp_pixmap = QPixmap()
                    if temp_pixmap.loadFromData(icon_response.content):
                        os.makedirs(os.path.dirname(icon_filename), exist_ok=True) 
                        with open(icon_filename, 'wb') as icon_file:
                            icon_file.write(icon_response.content)
                        logging.info(f"Successfully downloaded and saved game icon: {icon_filename}")
                    else:
                        logging.warning(f"Downloaded content for game icon {game_key} is not a valid image. Using default.")
                        icon_filename = default_icon_path
                        
                except requests.exceptions.RequestException as e: 
                    logging.error(f"Network error while downloading game icon for {game_key}: {e}")
                    icon_filename = default_icon_path
                except Exception as e:
                    logging.error(f"Error processing game icon for {game_key}: {e}", exc_info=True)
                    icon_filename = default_icon_path

            if not os.path.exists(icon_filename) and os.path.exists(default_icon_path):
                icon_filename = default_icon_path
                logging.info(f"Game icon for {game_key} not found or failed to download. Using default icon: {default_icon_path}")
            elif not os.path.exists(icon_filename):
                logging.warning(f"Game icon for {game_key} not found, and default icon {default_icon_path} is also missing. Using None for icon path.")
                icon_filename = None 

            server_widget = AccordionWidget(game_key, server_info, icon_filename, parent=self.content_widget)
            server_widget.toggled.connect(self.accordion_toggled)
            self.content_layout.addWidget(server_widget)
            self.game_widgets[game_key] = server_widget

            interval = self.settings.get(game_key, {}).get('interval', 60) * 1000
            timer = QTimer(self)
            timer.timeout.connect(lambda gk=game_key, sa=server_address: self.update_server_data(gk, sa))
            timer.start(interval)
            self.update_timers[game_key] = timer

            if expanded_count < max_expanded:
                server_widget.header_button.setChecked(True)
                server_widget.toggle() 
                expanded_count += 1
        
        self.content_layout.addStretch()
        self.adjust_layout_and_height()

    def apply_transparency_settings(self):
        """Применяет настройки прозрачности к центральному виджету."""
        transparency = self.settings.get('main_window_transparency', 128)
        self.central_widget.setStyleSheet(f"background-color: rgba(30, 30, 30, {transparency}); border-radius: 10px;")
        self.update() 

    def accordion_toggled(self, toggled_widget):
        """Обрабатывает событие переключения аккордеона.

        :param toggled_widget: Переключенный виджет.
        """
        for widget in self.game_widgets.values():
            if widget != toggled_widget and widget.header_button.isChecked():
                widget.header_button.setChecked(False)
                widget.toggle() 
        logging.debug("MainWindow.accordion_toggled: Relying on individual accordion animation.finished to adjust height.")


    def update_server_data(self, game_key, server_address): 
        """Обновляет данные о сервере и обновляет соответствующий виджет.

        :param game_key: Ключ игры.
        :param server_address: Полный адрес сервера (IP:Port).
        """
        try:
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
            logging.error(f"Unexpected error updating server data for {game_key} ({server_address}): {e}", exc_info=True)
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
        """Создает иконку в трее и меню."""
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = "icons/tray_icon.png" 
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            logging.warning(f"Tray icon not found at {icon_path}. Using default system icon.")
            if self.style():
                 self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))


        show_action = QAction("Показать", self)
        hide_action = QAction("Скрыть", self)
        settings_action = QAction("Настройки", self)
        quit_action = QAction("Выход", self)

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
        if not self.isVisible():
            self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.raise_()
        self.activateWindow()


    def hide_window(self):
        """Скрывает главное окно."""
        self.hide()

    def exit_app(self):
        """Корректный выход из приложения с удалением иконки из трея."""
        logging.info("Exit app called.")
        for timer in self.update_timers.values():
            timer.stop()

        for widget_key in list(self.game_widgets.keys()): 
            widget = self.game_widgets.pop(widget_key, None)
            if widget and hasattr(widget, 'ping_thread') and widget.ping_thread and widget.ping_thread.isRunning():
                widget.ping_thread.quit()
                widget.ping_thread.wait(1000) 

        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        
        QApplication.instance().quit()


    def closeEvent(self, event):
        """Обрабатывает событие закрытия окна приложения."""
        self.hide_window()
        event.ignore()


    def open_settings(self):
        """Открывает окно настроек."""
        if hasattr(self, 'settings_window_instance') and self.settings_window_instance and self.settings_window_instance.isVisible():
            self.settings_window_instance.raise_()
            self.settings_window_instance.activateWindow()
            return
        
        self.original_settings = copy.deepcopy(self.settings)
        self.settings_window_instance = SettingsWindow(self.game_list, self.settings, self)
        self.settings_window_instance.settings_changed.connect(self.apply_settings)
        self.settings_window_instance.settings_updated.connect(self.apply_temporary_settings)
        self.settings_window_instance.settings_reverted.connect(self.restore_original_settings)
        self.settings_window_instance.exec()


    def apply_settings(self):
        """Применяет новые настройки и сохраняет их в файл."""
        if hasattr(self, 'settings_window_instance') and self.settings_window_instance:
            new_settings = self.settings_window_instance.get_settings()
            self.settings.update(new_settings) 
            try:
                with open("settings.json", "w", encoding='utf-8') as f:
                    json.dump(self.settings, f, ensure_ascii=False, indent=4)
                logging.info("Settings saved successfully.")
            except IOError as e:
                logging.error(f"IOError saving settings to settings.json: {e}")
            except Exception as e:
                logging.error(f"Unexpected error saving settings: {e}", exc_info=True)

            new_width = self.settings.get('window_width', self.width())
            self.resize(new_width, self.height()) 
            
            self.reload_data() 
            self.adjust_layout_and_height() 
            logging.debug("Called adjust_layout_and_height explicitly after reload_data in apply_settings.")
            self.apply_transparency_settings() 
        else:
            logging.warning("apply_settings called but settings_window_instance is not available.")


    def apply_temporary_settings(self, temp_settings):
        """Применяет временные настройки.

        :param temp_settings: Словарь с временными настройками.
        """
        preview_settings = {**self.settings, **temp_settings}

        transparency = preview_settings.get('main_window_transparency', 128)
        self.central_widget.setStyleSheet(f"background-color: rgba(30, 30, 30, {transparency}); border-radius: 10px;")
        self.update() 

        new_width = preview_settings.get('window_width', self.width())
        if self.width() != new_width:
            self.resize(new_width, self.height())


    def restore_original_settings(self):
        """Восстанавливает оригинальные настройки."""
        self.settings = copy.deepcopy(self.original_settings) 
        self.apply_transparency_settings() 
        self.resize(self.settings.get('window_width', self.width()), self.height()) 

    def reload_data(self):
        """Перезагружает данные о серверах и обновляет интерфейс."""
        for timer in self.update_timers.values():
            timer.stop()
        self.update_timers.clear()

        while self.content_layout.count():
            item = self.content_layout.takeAt(0) 
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        self.game_widgets.clear()
        self.load_data() 

    def resizeEvent(self, event):
        """Обрабатывает изменение размера окна."""
        super().resizeEvent(event)

    def adjust_layout_and_height(self):
        if self.height_adjustment_pending:
            logging.debug("Height adjustment already pending, skipping.")
            return
        
        logging.debug("Scheduling height adjustment.")
        self.height_adjustment_pending = True
        QTimer.singleShot(0, self._perform_height_adjustment)

    def _perform_height_adjustment(self):
        logging.debug("Performing actual height adjustment.")
        current_width = self.width()
        
        ideal_height = self.height() 
        if self.layout:
            self.layout.invalidate()
            self.layout.activate()
            ideal_height = self.layout.sizeHint().height()
        else:
            logging.warning("_perform_height_adjustment: self.layout is None!")

        min_height_with_games_enabled = 150
        min_height_no_games_enabled = 100
        
        has_enabled_games = False
        if hasattr(self, 'game_list') and self.game_list and \
           hasattr(self, 'settings') and self.settings:
            for game_key in self.game_list:
                if isinstance(self.settings.get(game_key), dict) and \
                   self.settings[game_key].get('enabled', False):
                    has_enabled_games = True
                    break
        
        if has_enabled_games:
            ideal_height = max(ideal_height, min_height_with_games_enabled)
        else:
            if hasattr(self, 'add_games_button') and self.add_games_button.isVisible():
                 ideal_height = max(ideal_height, min_height_no_games_enabled)
            else: 
                 ideal_height = max(ideal_height, min_height_with_games_enabled) 


        min_h = self.minimumHeight() if self.minimumHeight() > 0 else 0
        max_h = self.maximumHeight() if self.maximumHeight() < 16777215 else 16777215 
        
        ideal_height = max(min_h, min(ideal_height, max_h))

        if self.height() != ideal_height or self.width() != current_width:
            self.resize(current_width, ideal_height)
        
        logging.debug(f"_perform_height_adjustment: W={current_width}, H={ideal_height}. Layout ideal H: {self.layout.sizeHint().height() if self.layout else 'N/A'}")
        
        self.height_adjustment_pending = False
