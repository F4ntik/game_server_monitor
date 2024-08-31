# ui/main_window.py

from PyQt6.QtWidgets import QMainWindow, QScrollArea, QWidget, QVBoxLayout, QLabel, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt
from core.server_manager import ServerManager
from ui.accordion_widget import AccordionWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Настройка главного окна
        self.setWindowTitle("Game Server Monitor")
        self.setGeometry(100, 100, 800, 600)

        # Основной виджет центрального окна
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной макет для центрального виджета
        self.layout = QVBoxLayout(central_widget)

        # Создание скроллируемой области
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_area.setWidget(scroll_content)
        self.layout.addWidget(scroll_area)

        # Макет для содержимого скроллируемой области
        content_layout = QVBoxLayout(scroll_content)

        # Инициализация менеджера серверов
        server_manager = ServerManager()
        server_manager.load_servers()

        # Создание виджетов аккордеонов для каждого сервера
        for ip_port, server_data in server_manager.servers.items():
            accordion = AccordionWidget(server_data)
            content_layout.addWidget(accordion)

        # Применение современных стилей к главному окну
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #232526, stop:1 #414345);
                color: #FFFFFF;
                font-family: Arial, sans-serif;
                font-size: 14px;
            }
            QLabel {
                color: #dcdcdc;
            }
        """)

        # Добавление тени к центральному виджету
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(Qt.GlobalColor.black)
        central_widget.setGraphicsEffect(shadow)

        # Показ уведомления о количестве загруженных серверов
        status_label = QLabel(f"Loaded {len(server_manager.servers)} servers.")
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(status_label)
