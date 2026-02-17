import sys
import os
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, ".."))

from src.utils.lifecycle import SingleInstanceLock
from src.utils.logger import setup_logging
from src.controller import AppController

from src.ui.tray import TrayIcon

def main():
    # 1. Setup Logging
    setup_logging()
    
    # 2. Single Instance Check
    lock = SingleInstanceLock()
    if not lock.try_lock():
        print("Another instance is already running.")
        sys.exit(1)
        
    # 3. High-DPI Scaling
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    # 4. Initialize App
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) # Keep app running in tray
    
    # 5. Startup Checks
    from PySide6.QtWidgets import QMessageBox
    import sounddevice as sd
    
    # Check Microphone
    try:
        sd.query_devices(kind='input')
    except Exception as e:
        QMessageBox.critical(None, "Startup Error", 
            f"No input device found or Audio subsystem failed.\n\nError: {e}\n\nPlease check your microphone settings.")
        sys.exit(1)
        
    # 6. Controller
    controller = AppController()
    
    # 7. Tray Icon
    tray_icon = TrayIcon(app)
    tray_icon.settings_requested.connect(controller.open_settings)
    tray_icon.restart_audio_requested.connect(controller.restart_audio)
    tray_icon.quit_requested.connect(app.quit)
    tray_icon.show()
    
    # Handle Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    # 8. Run
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
