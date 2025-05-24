import copy
import logging
from PyQt6.QtWidgets import (
    QDialog, QGridLayout, QGroupBox, QHBoxLayout, 
    QCheckBox, QSpinBox, QLabel, QPushButton, QSlider
)
from PyQt6.QtCore import Qt, pyqtSignal

class SettingsWindow(QDialog):
    """Окно настроек приложения."""
    settings_changed = pyqtSignal()
    settings_updated = pyqtSignal(dict)
    settings_reverted = pyqtSignal()

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
        self.settings = settings # This is a reference to MainWindow's settings
        self.original_settings = copy.deepcopy(settings) # Deep copy for revert
        self.setModal(True)
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
            if row > 5: # Adjust grid layout for many games
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
        self.window_width_spinbox.setMinimum(200) # Example minimum width
        self.window_width_spinbox.setMaximum(2000) # Example maximum width
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
        layout.addLayout(button_layout, 3, 1) # Centered buttons

    def update_transparency(self, value):
        """Обновляет уровень прозрачности основного окна.

        :param value: Уровень прозрачности (0-255).
        """
        self.main_window_transparency_label.setText(str(value))
        current_settings = self.get_settings() # Get all current UI settings
        self.settings_updated.emit(current_settings)


    def update_window_size(self, value):
        """Обновляет ширину окна.

        :param value: Ширина окна в пикселях.
        """
        current_settings = self.get_settings() # Get all current UI settings
        self.settings_updated.emit(current_settings)

    def save_settings(self):
        """Сохраняет текущие настройки и закрывает окно."""
        # The self.settings object in MainWindow is directly modified
        # by apply_temporary_settings via the settings_updated signal.
        # Here, we just need to signal that permanent save is requested.
        self.settings_changed.emit()
        self.close()

    def reject(self):
        """Отменяет изменения и восстанавливает оригинальные настройки."""
        # Restore the original settings to the main window's settings object
        self.settings_reverted.emit()
        super().reject()

    def get_settings(self):
        """Возвращает текущие настройки из интерфейса.

        :return: Словарь с текущими настройками.
        """
        current_ui_settings = {}
        for game_key, widgets in self.game_settings.items():
            current_ui_settings[game_key] = {
                'enabled': widgets['enabled'].isChecked(),
                'interval': widgets['interval'].value()
            }
        current_ui_settings['main_window_transparency'] = self.main_window_transparency.value()
        current_ui_settings['window_width'] = self.window_width_spinbox.value()
        return current_ui_settings
