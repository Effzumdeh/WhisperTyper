import logging
import time
import os
import threading
from typing import Optional
import numpy as np

from PySide6.QtCore import QObject, Signal, QThread, Slot, QTimer
from PySide6.QtWidgets import QApplication
from pynput import keyboard

from src.core.audio_service import AudioService
from src.core.inference import InferenceService
from src.core.text_injector import TextInjector
from src.ui.overlay import OverlayWidget
from src.ui.settings import SettingsDialog
from src.utils.config import config_manager
from src.utils import sound


logger = logging.getLogger(__name__)

class InferenceWorker(QObject):
    """
    Worker class to run inference in a separate QThread.
    """
    finished = Signal(str)
    
    def __init__(self, inference_service: InferenceService):
        super().__init__()
        self.inference_service = inference_service
        self.audio_data = None
        
    @Slot()
    def process(self):
        if self.audio_data is None:
            self.finished.emit("")
            return
            
        text = self.inference_service.transcribe(self.audio_data)
        self.finished.emit(text)

class AppController(QObject):
    """
    Main Controller:
    - Listens to Global Hotkeys
    - Controls AudioRecording
    - Updates Overlay
    - Triggers Inference
    """
    

    model_loaded = Signal(bool)
    ui_update_signal = Signal(str, str)
    
    def __init__(self):
        super().__init__()
        
        # Services
        self.audio_service = AudioService()
        self.audio_service.start_listening()
        self.inference_service = InferenceService()
        self.text_injector = TextInjector()
        
        # UI
        self.overlay = OverlayWidget()
        self.overlay.show()
        
        # Connect UI Signal
        self.ui_update_signal.connect(self.overlay.set_state)
        
        
        # State
        self.is_recording = False
        
        # Load Model in background
        self.ui_update_signal.emit("processing", "Loading Model...")
        self.inference_service.load_model(on_complete=self._on_model_loaded)
        
        # Hotkeys
        self.listener = None
        self.currently_pressed = set()
        self.target_keys = set()
        self._load_hotkey_config()
        self._start_hotkey_listener()
        
        # Connect Signals
        self.model_loaded.connect(self._handle_model_loaded)
        
    def _on_model_loaded(self, success: bool):
        # Called from background thread
        self.model_loaded.emit(success)

    @Slot(bool)
    def _handle_model_loaded(self, success: bool):
        if success:
            self.ui_update_signal.emit("idle", "Ready")
        else:
            self.ui_update_signal.emit("error", "Model Load Failed")
            sound.play_error_sound()

    def _load_hotkey_config(self):
        hotkey_str = config_manager.config.hotkey
        self.target_keys = self._parse_hotkey(hotkey_str)
        logger.info(f"Loaded hotkey: {self.target_keys}")

    def _parse_hotkey(self, hotkey_str: str):
        """
        Parses '<ctrl>+<alt>+s' into a set of pynput keys.
        """
        keys = set()
        parts = hotkey_str.lower().split('+')
        for part in parts:
            part = part.strip()
            if part == '<ctrl>': keys.add(keyboard.Key.ctrl_l) # We normalize to left in listener
            elif part == '<alt>': keys.add(keyboard.Key.alt_l)
            elif part == '<shift>': keys.add(keyboard.Key.shift)
            elif part == '<cmd>' or part == '<win>': keys.add(keyboard.Key.cmd)
            else:
                # Char key
                if len(part) == 1:
                    keys.add(keyboard.KeyCode(char=part))
        return keys

    def _start_hotkey_listener(self):
        """
        Starts the global hotkey listener.
        Logic: 
        - Configured Hotkey -> Start/Stop Recording
        - OR: Press -> Start, Release -> Stop?
        
        User request: 
        "When Hotkey is pressed -> start(), ... released -> stop()"
        "Panic Button: Key.esc"
        """
        
        # We need to parse the hotkey string e.g. "<ctrl>+<alt>+s"
        # pynput.keyboard.GlobalHotKeys expects a mapping.
        # But for "Press and Hold", GlobalHotKeys is not ideal, it triggers on "activation".
        # We need `pynput.keyboard.Listener` to detect key_down and key_up of specific keys.
        
        # However, making a robust "Press and Hold" for complex combinations like Ctrl+Alt+S is hard with raw listener.
        # Simplified approach for "Press and Hold":
        # - Code assumes a single key for PTT (Push To Talk) OR we implement a toggle?
        # User said: "Manual Stop (User releases Hotkey)". This implies Push-To-Talk.
        # And "Logic: When Hotkey is pressed -> ... When Hotkey is released -> ..."
        
        # Supporting "<ctrl>+<alt>+s" as PTT is tricky because of key repeats and partial releases.
        # Let's stick to the requested logic but maybe simplify default hotkey to something simpler like F8 or similar if complex combos fail.
        # But let's try to implement robust PTT for the configured hotkey.
        
        # Current config default: "<ctrl>+<alt>+s"
        
        hotkey_str = config_manager.config.hotkey
        
        # Pynput GlobalHotKeys is for triggers.
        # To do PTT, we might use GlobalHotKeys to detect "press" (on_activate), 
        # but detecting "release" of the COMBO is not supported natively.
        
        # HACK / STRATEGY: 
        # Use GlobalHotKeys to START recording.
        # Then use a raw Listener to wait for ANY key release that is part of the combo? 
        # Or just wait for the main key release.
        
        # Let's try to parse the hotkey and check states.
        # For this prototype, let's assume the user might want TOGGLE if it's a combo, 
        # OR PTT if it's a single key. 
        # BUT the user EXPLICITLY asked for "Release Hotkey" -> Stop.
        
        # Let's use `GlobalHotKeys` for the activation (Start).
        # And for Stop, we need to know when it is released.
        # This is quite complex for combos.
        self.target_keys = self._parse_hotkey(hotkey_str)
        logger.info(f"Loaded hotkey: {self.target_keys}")

    def _parse_hotkey(self, hotkey_str: str):
        """
        Parses '<ctrl>+<alt>+s' into a set of pynput keys.
        """
        keys = set()
        parts = hotkey_str.lower().split('+')
        for part in parts:
            part = part.strip()
            if part == '<ctrl>': keys.add(keyboard.Key.ctrl_l) # We normalize to left in listener
            elif part == '<alt>': keys.add(keyboard.Key.alt_l)
            elif part == '<shift>': keys.add(keyboard.Key.shift)
            elif part == '<cmd>' or part == '<win>': keys.add(keyboard.Key.cmd)
            else:
                # Char key
                if len(part) == 1:
                    keys.add(keyboard.KeyCode(char=part))
        return keys

    def _start_hotkey_listener(self):
        if self.listener:
            try:
                self.listener.stop()
            except: pass
            self.listener = None
            
        self.listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.listener.start()

    def _normalize_key(self, key):
        # Maps right modifiers to left to match our simple parser
        if key == keyboard.Key.ctrl_r: return keyboard.Key.ctrl_l
        if key == keyboard.Key.alt_r: return keyboard.Key.alt_l
        if key == keyboard.Key.shift_r: return keyboard.Key.shift
        return key

    def _on_key_press(self, key):
        # Normalize char keys to lowercase for robust matching
        if hasattr(key, 'char') and key.char:
             try:
                 key = keyboard.KeyCode(char=key.char.lower())
             except Exception:
                 pass
             
        # Normalize modifiers
        key_norm = self._normalize_key(key)
        self.currently_pressed.add(key_norm)
        
        # logger.debug(f"Key Pressed: {key} -> {key_norm}. Current: {self.currently_pressed}")
        
        if self.target_keys.issubset(self.currently_pressed):
            if not self.is_recording:
                logger.info(f"Hotkey Triggered! Target matched: {self.target_keys}")
                self._start_recording()

    def _on_key_release(self, key):
        # Normalize char keys to lowercase
        if hasattr(key, 'char') and key.char:
             try:
                 key = keyboard.KeyCode(char=key.char.lower())
             except Exception:
                 pass

        key_norm = self._normalize_key(key)
        
        if key_norm in self.currently_pressed:
            self.currently_pressed.remove(key_norm)
            
        # If we were recording and ANY key of the combo is released, we stop.
        if self.is_recording:
            # Check if combo is still held
            if not self.target_keys.issubset(self.currently_pressed):
                logger.info(f"Hotkey Released! Stopping. Needed: {self.target_keys}, Have: {self.currently_pressed}")
                self._stop_recording()

    def _is_key_esc(self, key):
        return key == keyboard.Key.esc

    def _start_recording(self):
        self.is_recording = True
        self.ui_update_signal.emit("recording", "Listening...")
        logger.info("Start Recording")
        
        # Start Audio Capture
        # We need to make sure AudioService captures the pre-roll
        self.audio_service.capture_snapshot_preroll()
        self.audio_service.start_capture()

    def _stop_recording(self):
        self.is_recording = False
        logger.info("Stop Recording")
        
        # Stop Audio Capture
        audio_data = self.audio_service.stop_capture()
        logger.info(f"Captured audio blocks: {len(audio_data)}")
        
        # DEBUG: Save WAV
        if config_manager.config.debug_mode:
            try:
                import wave
                import struct
                # scale float32 to int16
                audio_int16 = (audio_data * 32767).astype(int)
                audio_int16 = np.clip(audio_int16, -32768, 32767)
                
                log_dir = config_manager.paths.data_dir / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                wav_path = log_dir / "last_recording.wav"
                
                with wave.open(str(wav_path), "w") as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(16000)
                    f.writeframes(audio_int16.tobytes())
                logger.debug(f"Saved debug recording to {wav_path}")
            except Exception as e:
                logger.error(f"Failed to save debug wav: {e}")
        
        # Start Inference
        self.ui_update_signal.emit("processing", "Processing...")
        
        if len(audio_data) == 0:
             logger.info("No audio data caught")
             self.overlay.set_state("idle", "Ready")
             return

        threading.Thread(target=self._run_inference, args=(audio_data,)).start()

    def _restart_audio(self):
        """Restarts the audio service, useful for hot-plugging or config change."""
        logger.info("Restarting audio service...")
        self.audio_service.stop_listening()
        # Small delay?
        time.sleep(0.1)
        self.audio_service.start_listening()
        logger.info("Audio service restarted.")

    # Public slots for Tray Icon
    @Slot()
    def open_settings(self):
        self.settings_dialog = SettingsDialog()
        self.settings_dialog.config_changed.connect(self._on_config_changed)
        self.settings_dialog.show()
        
    @Slot()
    def restart_audio(self):
        self._restart_audio()
        
    @Slot()
    def _on_config_changed(self):
        logger.info("Configuration changed. Applying updates...")
        cfg = config_manager.config
        
        # 1. Hotkey
        self._load_hotkey_config()
        self._start_hotkey_listener()
        
        # 2. Model
        # Check if model config changed? 
        # For now, simplistic reload if we had a way to check.
        # But inference service handles lazy loading. 
        # If we really want to switch model, we might need inference_service.reload?
        # InferenceService.load_model() logic handles unloading if model exists.
        # So we can just call load_model again.
        
        # Determine if we need to reload model
        current_model_config = (cfg.model_size, cfg.compute_type)
        if hasattr(self, 'last_model_config') and current_model_config != self.last_model_config:
            logger.info("Model config changed. Reloading...")
            self.last_model_config = current_model_config
            self.ui_update_signal.emit("processing", "Loading Model...")
            self.inference_service.load_model(on_complete=self._on_model_loaded)
            
        # 3. Autostart
        from src.utils import lifecycle
        if cfg.autostart:
            lifecycle.install_startup_shortcut()
        else:
            lifecycle.remove_startup_shortcut()
            
        # 4. Audio Device
        self._restart_audio()

    def _run_inference(self, audio_data):
        try:
            text = self.inference_service.transcribe(
                audio_data,
                language=config_manager.config.language if config_manager.config.language != "auto" else None,
                initial_prompt=config_manager.config.initial_prompt
            )
            logger.info(f"Inference finished. Text: '{text}'")
            
            if text:
                # Inject Text
                self.text_injector.inject_text(text)
            else:
                logger.info("Transcribed text is empty.")
                
            self.ui_update_signal.emit("idle", "Ready")
            
        except Exception as e:
            logger.error(f"Inference Error: {e}")
            self.ui_update_signal.emit("error", "Error: Transcription Failed")
            # We could emit the specific error but "Transcription Failed" is cleaner for overlay
            # Optionally show brief error if it's short?
            # self.ui_update_signal.emit("error", f"Err: {str(e)[:20]}") 
            # Sticking to safe generic message for overlay, logs have details.

    def _on_panic(self):
        if self.is_recording:
            logger.info("Panic Button Pressed!")
            sound.play_cancel_sound()
            self.is_recording = False
            self.audio_service.stop_capture() # Just to reset flags
            # self.audio_service.clear_buffer() # No need in new logic
            self.ui_update_signal.emit("idle", "Cancelled")

    def _on_model_loaded(self, success):
        """Callback from inference service."""
        if success:
            logger.info("Model loaded callback received.")
            self.ui_update_signal.emit("idle", "Ready")
            # Start Audio Listening now that model is ready
            self.audio_service.start_listening()
        else:
            self.ui_update_signal.emit("error", "Model Load Failed")
