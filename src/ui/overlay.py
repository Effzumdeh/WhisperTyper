import sys
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QApplication
from PySide6.QtCore import Qt, QTimer, Property, QPoint, Slot
from PySide6.QtGui import QPainter, QColor, QFont, QBrush, QTransform

from src.ui.resources import Resources

class OverlayWidget(QWidget):
    """
    A non-intrusive overlay widget that stays on top and does not accept focus.
    """
    def __init__(self):
        super().__init__()
        
        # Window Flags
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool | 
            Qt.WindowDoesNotAcceptFocus |
            Qt.WindowTransparentForInput # Optional: if we want clicks to pass through entirely, but we might want to move it?
            # User said: "WindowDoesNotAcceptFocus so the user keeps focus on their target application"
            # If we want to allow moving the overlay, we need to accept mouse events but not focus.
            # But usually 'WindowTransparentForInput' makes it unclickable.
            # Let's stick to requested flags.
        )
        
        # Transparent background for the window, but we will paint a rounded rect
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Data
        self._state = "idle" # idle, recording, processing, error
        
        # Layout
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(15, 10, 15, 10)
        
        # Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        self.update_icon(Resources.SVG_MIC_IDLE)
        
        # Status Text
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        
        self.main_layout.addWidget(self.icon_label)
        self.main_layout.addWidget(self.status_label)
        
        # Styling
        self.setStyleSheet("""
            QLabel { font-family: 'Segoe UI', sans-serif; }
        """)
        
        # Spinner Animation
        self.spinner_angle = 0
        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self._rotate_spinner)
        
        # Position (Bottom Center default)
        self.resize(200, 60)
        self._center_position()
        
    def _center_position(self):
        screen = QApplication.primaryScreen()
        geom = screen.availableGeometry()
        x = geom.width() // 2 - self.width() // 2
        y = geom.height() - self.height() - 100 # 100px from bottom
        self.move(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        bg_color = QColor(0, 0, 0, 180) # Semi-transparent black
        if self._state == "recording":
            bg_color = QColor(60, 0, 0, 200) # Reddish tint
        
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        rect = self.rect()
        painter.drawRoundedRect(rect, 15, 15)

    @Slot(str, str)
    def set_state(self, state: str, message: str = ""):
        print(f"Overlay set_state: {state} - {message}") # Debug print
        self._state = state
        self.status_label.setText(message)
        self.spinner_timer.stop()
        
        if state == "idle":
            self.update_icon(Resources.SVG_MIC_IDLE)
            self.status_label.setText("Ready")
            self.status_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        elif state == "recording":
            self.update_icon(Resources.SVG_MIC_RECORDING)
            # Only reset text if we are just entering recording state and don't have a message override
            if not message:
                 self.status_label.setText("Listening...")
            else:
                 self.status_label.setText(message)
            self.status_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        elif state == "processing":
            self.update_icon(Resources.SVG_SPINNER)
            self.status_label.setText("Processing..." if not message else message)
            self.status_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
            self.spinner_timer.start(50)
        elif state == "error":
             self.update_icon(Resources.SVG_MIC_IDLE) # Or error icon
             self.status_label.setText(f"Error: {message}")
             self.status_label.setStyleSheet("color: #ff5555; font-weight: bold; font-size: 14px;")
             
        self.adjustSize()
        self._center_position()
        self.update() # Trigger repaint for background color

    @Slot(str)
    def set_preview_text(self, text: str):
        """Updates the overlay with live preview text."""
        if self._state != "recording":
            return
            
        if not text:
            # If empty, revert to Listening...
            if self.status_label.text() != "Listening...":
                self.status_label.setText("Listening...")
                self.status_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
                self.adjustSize()
                self._center_position()
            return
            
        # Avoid repainting if text matches
        if self.status_label.text() == text:
            return
            
        self.status_label.setText(text)
        # Visual cue for preview: Italic and slightly gray?
        self.status_label.setStyleSheet("color: #dddddd; font-style: italic; font-size: 14px;")
        
        self.adjustSize()
        self._center_position()

    @Slot()
    def clear_preview(self):
        if self._state == "recording":
             self.status_label.setText("Listening...")
             self.status_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
             self.adjustSize()
             self._center_position()

    def update_icon(self, svg_data):
        self.icon_label.setPixmap(Resources.get_pixmap(svg_data, 24))

    def _rotate_spinner(self):
        # Rotating a static SVG is tricky with just QPixmap. 
        # Ideally we rotate the painter drawing the pixmap.
        # For simplicity, we'll just keep the spinner static or implement rotation later.
        # User asked for "Implement a method to animate the spinner".
        
        self.spinner_angle = (self.spinner_angle + 30) % 360
        
        # Create rotated pixmap
        src_pixmap = Resources.get_pixmap(Resources.SVG_SPINNER, 24)
        rotated_pixmap = src_pixmap.transformed(
            QTransform().rotate(self.spinner_angle), 
            Qt.SmoothTransformation
        )
        
        # Center crop/adjust might be needed if it changes size, but 24x24 rotation usually fits in bounding box if circular
        self.icon_label.setPixmap(rotated_pixmap)
