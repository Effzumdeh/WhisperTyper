import logging
import time
import threading
import pyperclip
from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)

class TextInjector:
    """
    Handles text injection by simulating clipboard paste.
    """
    def __init__(self):
        self.keyboard = Controller()
        
    def inject_text(self, text: str):
        """
        Injects text into the active application.
        1. Backs up clipboard.
        2. Sets clipboard to text.
        3. Simulates Ctrl+V.
        4. Restores clipboard.
        """
        if not text:
            return

        def _inject():
            try:
                # 1. Backup
                try:
                    original_clipboard = pyperclip.paste()
                except Exception:
                    original_clipboard = ""
                
                # 2. Set Content
                pyperclip.copy(text)
                
                # 3. Simulate Paste
                # wait a bit for clipboard to update
                time.sleep(0.1) 
                
                with self.keyboard.pressed(Key.ctrl):
                    self.keyboard.press('v')
                    self.keyboard.release('v')
                    
                # 4. Restore (wait for paste to consume clipboard)
                time.sleep(0.2)
                pyperclip.copy(original_clipboard)
                
                logger.info(f"Injected text: {text[:20]}...")
                
            except Exception as e:
                logger.error(f"Text injection failed: {e}")

        # Run in thread to not block any caller
        threading.Thread(target=_inject, daemon=True).start()
