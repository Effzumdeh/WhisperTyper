from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Signal, QObject
from src.ui.resources import Resources

class TrayIcon(QSystemTrayIcon):
    # Signals to Controller
    settings_requested = Signal()
    restart_audio_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIcon(Resources.get_icon(Resources.ICON_TRAY))
        self.setToolTip("WhisperTyper")
        
        # Menu
        self.menu = QMenu()
        
        # Actions
        self.action_settings = QAction("Settings", self)
        self.action_settings.triggered.connect(self.settings_requested.emit)
        
        self.action_restart_audio = QAction("Restart Audio Engine", self)
        self.action_restart_audio.triggered.connect(self.restart_audio_requested.emit)
        
        self.action_quit = QAction("Quit", self)
        self.action_quit.triggered.connect(self.quit_requested.emit)
        
        # Add to Menu
        self.menu.addAction(self.action_settings)
        self.menu.addSeparator()
        self.menu.addAction(self.action_restart_audio)
        self.menu.addSeparator()
        self.menu.addAction(self.action_quit)
        
        self.setContextMenu(self.menu)
        
        # Activation (Click)
        self.activated.connect(self._on_activated)
        
    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.settings_requested.emit()
