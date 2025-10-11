from PyQt6.QtWidgets import QWidget, QStyleOptionSizeGrip, QStyle
from PyQt6.QtGui import QPainter
from PyQt6.QtCore import Qt

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
        # Draw the grip using the style, ensuring it respects the parent's style.
        self.style().drawControl(QStyle.ControlElement.CE_SizeGrip, option, painter, self)

    def mousePressEvent(self, event):
        """Обрабатывает нажатие мыши для начала изменения размера."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Store the initial mouse global position and window geometry
            self.mouse_press_offset = event.globalPosition().toPoint()
            if self.window(): # Ensure we have a window
                 self.initial_window_geometry = self.window().geometry()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Обрабатывает перемещение мыши для изменения размера окна."""
        if event.buttons() == Qt.MouseButton.LeftButton and \
           self.mouse_press_offset is not None and \
           self.initial_window_geometry is not None:
            
            window_to_resize = self.window()
            if window_to_resize:
                delta = event.globalPosition().toPoint() - self.mouse_press_offset
                
                # Start with a copy of the initial geometry
                new_geo = self.initial_window_geometry.translated(0,0) # Create a copy at the same top-left
                
                new_geo.setWidth(self.initial_window_geometry.width() + delta.x())
                new_geo.setHeight(self.initial_window_geometry.height() + delta.y())

                # Respect minimum dimensions of the window
                min_w = window_to_resize.minimumWidth()
                min_h = window_to_resize.minimumHeight()
                
                if new_geo.width() < min_w:
                    new_geo.setWidth(min_w)
                if new_geo.height() < min_h:
                    new_geo.setHeight(min_h)
                
                # Respect maximum dimensions if set (using QWidget's default max)
                max_w = window_to_resize.maximumWidth() 
                max_h = window_to_resize.maximumHeight()

                if new_geo.width() > max_w:
                    new_geo.setWidth(max_w)
                if new_geo.height() > max_h:
                    new_geo.setHeight(max_h)
                
                # Only apply if geometry changes to avoid unnecessary updates
                if window_to_resize.geometry() != new_geo:
                    window_to_resize.setGeometry(new_geo)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Обрабатывает отпускание кнопки мыши."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_press_offset = None
            self.initial_window_geometry = None
        super().mouseReleaseEvent(event)
