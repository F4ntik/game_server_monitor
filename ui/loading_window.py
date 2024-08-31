# ui/loading_window.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar

class LoadingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Loading Game Server Monitor")
        self.setGeometry(100, 100, 400, 200)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.label = QLabel("Initializing...")
        self.layout.addWidget(self.label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.layout.addWidget(self.progress_bar)

    def update_progress(self, progress, message):
        self.progress_bar.setValue(progress)
        self.label.setText(message)
