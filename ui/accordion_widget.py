# ui/accordion_widget.py

from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, Qt
from PyQt6.QtGui import QPixmap  # Импорт для работы с изображениями
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFrame

class AccordionWidget(QWidget):
    def __init__(self, server_data, parent=None):
        super().__init__(parent)

        self.is_expanded = False
        self.server_data = server_data

        # Основной макет
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Кнопка-заголовок для аккордеона
        self.toggle_button = QPushButton()
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.setStyleSheet(self.button_style())
        self.toggle_button.setFixedHeight(60)
        self.layout.addWidget(self.toggle_button)

        # Макет для содержимого свернутого вида
        self.header_layout = QVBoxLayout()
        self.toggle_button.setLayout(self.header_layout)

        # Иконка игры
        self.game_icon_label = QLabel()
        self.game_icon_label.setFixedSize(40, 40)
        self.header_layout.addWidget(self.game_icon_label)

        # Название карты
        self.map_name_label = QLabel(f"Map: {server_data['current_map']}")
        self.header_layout.addWidget(self.map_name_label)

        # Количество игроков
        self.player_count_label = QLabel(f"{server_data['num_players']}/{server_data['max_players']}")
        self.header_layout.addWidget(self.player_count_label)

        # Пинг
        self.ping_label = QLabel(f"Ping: {server_data.get('ping', 'N/A')}ms")
        self.header_layout.addWidget(self.ping_label)

        self.header_layout.addStretch()

        # Контейнер для содержимого развернутого вида
        self.content_widget = QFrame()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_widget.setLayout(self.content_layout)
        self.content_widget.setMaximumHeight(0)
        self.content_widget.setVisible(False)
        self.content_widget.setStyleSheet(AccordionWidget.content_style())  # Исправленный вызов метода
        self.layout.addWidget(self.content_widget)

        # Настройка анимации
        self.animation = QPropertyAnimation(self.content_widget, b"maximumHeight")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Подключение кнопки к переключению
        self.toggle_button.clicked.connect(self.toggle)

        # Установка данных сервера в развернутый вид
        self.setExpandedContent()

    def toggle(self):
        """Переключает состояние аккордеона (раскрыть/закрыть) с анимацией."""
        if self.toggle_button.isChecked():
            self.is_expanded = True
            self.content_widget.setVisible(True)
            self.animation.setStartValue(0)
            self.animation.setEndValue(300)  # Высота развернутого содержимого

            # Применение стиля для развернутого вида
            self.toggle_button.setStyleSheet(self.expanded_button_style())
            self.header_layout.removeWidget(self.game_icon_label)
            self.header_layout.removeWidget(self.map_name_label)
            self.header_layout.removeWidget(self.player_count_label)
            self.header_layout.removeWidget(self.ping_label)
        else:
            self.is_expanded = False
            self.animation.setStartValue(self.content_widget.maximumHeight())
            self.animation.setEndValue(0)

            # Возвращаем стиль для свернутого вида
            self.toggle_button.setStyleSheet(self.button_style())
            self.header_layout.addWidget(self.game_icon_label)
            self.header_layout.addWidget(self.map_name_label)
            self.header_layout.addWidget(self.player_count_label)
            self.header_layout.addWidget(self.ping_label)

        self.animation.start()
        self.animation.finished.connect(self._finalize_animation)

    def _finalize_animation(self):
        """Финализирует видимость содержимого после завершения анимации."""
        if not self.toggle_button.isChecked():
            self.content_widget.setVisible(False)
        self.animation.finished.disconnect(self._finalize_animation)

    def setExpandedContent(self):
        """Устанавливает развернутое содержимое."""
        map_image_label = QLabel()
        map_image_path = f"resources/maps/{self.server_data['current_map']}.jpg"  # Укажите путь к файлу карты
        map_image_label.setPixmap(QPixmap(map_image_path).scaled(100, 100))
        self.content_layout.addWidget(map_image_label)

        map_name_label = QLabel(f"Map: {self.server_data['current_map']}")
        self.content_layout.addWidget(map_name_label)

        players_label = QLabel("Players: \n" + "\n".join([f"Player{i+1}" for i in range(int(self.server_data['num_players']))]))
        self.content_layout.addWidget(players_label)

        ping_label = QLabel(f"Ping: {self.server_data.get('ping', 'N/A')}ms")
        self.content_layout.addWidget(ping_label)

    def setGameIcon(self, icon_path):
        """Устанавливает иконку игры."""
        pixmap = QPixmap(icon_path).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio)
        self.game_icon_label.setPixmap(pixmap)

    @staticmethod
    def button_style():
        """Возвращает строку CSS для стилизации кнопки."""
        return """
            QPushButton {
                background-color: #3b3b3b;
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                padding: 10px;
                text-align: left;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
        """

    @staticmethod
    def expanded_button_style():
        """Возвращает строку CSS для стилизации развернутой кнопки."""
        return """
            QPushButton {
                background-color: #5a5a5a;
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                padding: 10px;
                text-align: left;
                font-size: 16px;
                font-weight: bold;
            }
        """

    @staticmethod
    def content_style():
        """Возвращает строку CSS для стилизации содержимого."""
        return """
            QFrame {
                background-color: #444444;
                border: 1px solid #5a5a5a;
                border-radius: 5px;
                padding: 10px;
                color: #ffffff;
            }
            QLabel {
                font-size: 14px;
                color: #dcdcdc;
            }
        """
