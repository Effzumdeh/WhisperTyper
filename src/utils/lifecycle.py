import sys
import os
import logging
from pathlib import Path

# Fallback to no-dependency approach: creating a .vbs or .bat is easiest but .lnk is better.
# We use a simple VBScript to create the shortcut without pywin32/winshell.

logger = logging.getLogger(__name__)

def get_startup_path() -> Path:
    return Path(os.getenv('APPDATA')) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

def install_startup_shortcut():
    """Creates a shortcut in the Windows Startup folder."""
    try:
        startup_folder = get_startup_path()
        shortcut_path = startup_folder / "WhisperTyper.lnk"
        
        target = sys.executable
        # If frozen (PyInstaller), target is the exe.
        # If script, target is python.exe and args are the script.
        
        cwd = os.getcwd()
        
        if getattr(sys, 'frozen', False):
             app_path = sys.executable
             args = ""
        else:
             # Running as script
             app_path = sys.executable
             # We assume main.py is entry point
             script_path = os.path.join(cwd, "src", "main.py")
             args = f'"{script_path}"'
        
        # Create shortcut using VBScript hack to avoid pywin32 dependency if possible
        vbs_script = f"""
        Set oWS = WScript.CreateObject("WScript.Shell")
        sLinkFile = "{shortcut_path}"
        Set oLink = oWS.CreateShortcut(sLinkFile)
        oLink.TargetPath = "{app_path}"
        oLink.Arguments = "{args}"
        oLink.WorkingDirectory = "{cwd}"
        oLink.Save
        """
        
        vbs_path = Path(os.environ["TEMP"]) / "create_shortcut.vbs"
        with open(vbs_path, "w") as f:
            f.write(vbs_script)
            
        os.system(f'cscript /nologo "{vbs_path}"')
        os.remove(vbs_path)
        logger.info(f"Startup shortcut created at {shortcut_path}")
        
    except Exception as e:
        logger.error(f"Failed to create startup shortcut: {e}")

def remove_startup_shortcut():
    """Removes the shortcut from the Windows Startup folder."""
    try:
        startup_folder = get_startup_path()
        shortcut_path = startup_folder / "WhisperTyper.lnk"
        if shortcut_path.exists():
            os.remove(shortcut_path)
            logger.info("Startup shortcut removed.")
    except Exception as e:
        logger.error(f"Failed to remove startup shortcut: {e}")

from PySide6.QtCore import QLockFile, QDir

class SingleInstanceLock:
    """Ensures only one instance of the application runs."""
    
    def __init__(self, app_name: str = "WhisperTyper"):
        self.lock_file = QLockFile(str(Path(QDir.tempPath()) / f"{app_name}.lock"))
        
    def try_lock(self) -> bool:
        if self.lock_file.tryLock(100):
            return True
        return False
        
    def unlock(self):
        self.lock_file.unlock()

def resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(os.getcwd())

    return base_path / relative_path
