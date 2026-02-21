import logging
import time
import os
import threading
from typing import Optional
import numpy as np
import re

from PySide6.QtCore import QObject, Signal, QThread, Slot, QTimer
from PySide6.QtWidgets import QApplication
from pynput import keyboard

from src.core.audio_service import AudioService
from src.core.inference import InferenceService
from src.core.text_injector import TextInjector
from src.core.llm_processor import LLMClient
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
    preview_update_signal = Signal(str) # For Live Preview
    
    # Signals to bridge pynput thread -> Main Thread
    start_recording_signal = Signal()
    stop_recording_signal = Signal()
    
    def __init__(self):
        super().__init__()
        
        # Services
        self.audio_service = AudioService()
        self.audio_service.start_listening()
        self.inference_service = InferenceService()
        self.text_injector = TextInjector()
        
        # Locks & State for Inference
        self.inference_lock = threading.Lock()
        
        # UI
        self.overlay = OverlayWidget()
        self.overlay.show()
        
        # Connect UI Signal
        self.ui_update_signal.connect(self.overlay.set_state)
        self.preview_update_signal.connect(self.overlay.set_preview_text)
        
        # Connect Threading Signals
        self.start_recording_signal.connect(self._on_start_recording_slot)
        self.stop_recording_signal.connect(self._on_stop_recording_slot)
        
        # Live Preview Timer
        self.preview_timer = QTimer()
        self.preview_timer.setInterval(1000) # 1 second tick
        self.preview_timer.timeout.connect(self._on_preview_tick)
        self.is_preview_processing = False
        
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
                # Emit signal instead of calling directly
                self.start_recording_signal.emit()

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
                # Emit signal instead of calling directly
                self.stop_recording_signal.emit()

    def _is_key_esc(self, key):
        return key == keyboard.Key.esc

    # Deprecated direct calls from pynput (Removed/Renamed)
    # def _start_recording(self): ...
    
    @Slot()
    def _on_start_recording_slot(self):
        """Main thread slot to start recording."""
        # Double check state in case of rapid fires
        if self.is_recording: return
        
        self.is_recording = True
        self.ui_update_signal.emit("recording", "Listening...")
        self.preview_update_signal.emit("") # Clear previous preview
        logger.info("Start Recording (Main Thread)")
        
        # Start Audio Capture
        self.audio_service.capture_snapshot_preroll()
        self.audio_service.start_capture()
        
        # Start Live Preview Timer if enabled
        # Safe to call here as we are on Main Thread
        if getattr(config_manager.config, 'live_preview', False):
            self.is_preview_processing = False
            self.preview_timer.start()

    @Slot()
    def _on_stop_recording_slot(self):
        """Main thread slot to stop recording."""
        if not self.is_recording: return
        
        self.is_recording = False
        
        # Stop Preview Timer immediately (Safe on Main Thread)
        self.preview_timer.stop()
        
        logger.info("Stop Recording (Main Thread)")
        
        # Stop Audio Capture
        audio_data = self.audio_service.stop_capture()
        logger.info(f"Captured audio blocks: {len(audio_data)}")
        
        # DEBUG: Save WAV
        try:
            import wave
            import struct
            # scale float32 to int16
            audio_int16 = (audio_data * 32767).astype(int)
            audio_int16 = np.clip(audio_int16, -32768, 32767)
            
            with wave.open("debug_last_recording.wav", "w") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(16000)
                f.writeframes(audio_int16.tobytes())
            logger.debug(f"Saved debug recording to {os.path.abspath('debug_last_recording.wav')}")
        except Exception as e:
            logger.error(f"Failed to save debug wav: {e}")
        
        # Start Inference
        self.ui_update_signal.emit("processing", "Processing...")
        
        if len(audio_data) == 0:
             logger.info("No audio data caught")
             self.overlay.set_state("idle", "Ready")
             return

        # Start Final Inference in Thread
        threading.Thread(target=self._run_inference, args=(audio_data,)).start()

    def _on_preview_tick(self):
        """Called every second to update preview."""
        if self.is_preview_processing:
            return # Drop frame if previous is still running
            
        self.is_preview_processing = True
        
        # Get Current Buffer (Thread Safe)
        audio = self.audio_service.get_current_buffer()
        
        # Run Partial Inference in background
        threading.Thread(target=self._run_preview_inference, args=(audio,), daemon=True).start()

    def _run_preview_inference(self, audio_data):
        try:
            # Acquire Lock to prevent collision with final inference (or other partials)
            # Use a timeout or just block? Blocking is fine if short. 1s interval.
            # If final inference starts, it will block until this is done. Safe.
            with self.inference_lock:
                 # Check if we are still recording?
                 pass
                 
                 text = self.inference_service.transcribe_partial(audio_data)
                 
            if text:
                 # Smart Truncation: Hide completed sentences if new context is established
                 refined_text = self._process_preview_text(text)
                 self.preview_update_signal.emit(refined_text)
                 
        except Exception as e:
            logger.error(f"Preview inference error: {e}")
        finally:
            self.is_preview_processing = False

    def _process_preview_text(self, text: str) -> str:
        """
        Trims completed sentences from the preview if a new sentence 
        has enough context (> 3 words).
        """
        if not text: return ""
        
        # Split by sentence terminators (., ?, !)
        # Robust approach: Find all sentence endings.
        import re
        
        sentences = re.split(r'(?<=[.?!])\s+', text.strip())
        
        if len(sentences) <= 1:
            return text
            
        # We have at least 2 parts.
        # Check the last part (the "active" sentence)
        last_sentence = sentences[-1]
        
        # Count words
        words = last_sentence.split()
        
        # If the last incomplete sentence has > 3 words, we show only it.
        # "Hello world. This is a big" (4 words) -> "This is a big"
        if len(words) > 3:
             # Prefix with ellipsis to show continuation/truncation
             return "... " + last_sentence
        else:
             # Not enough context yet. Show the previous sentence + current.
             # "Hello world. This is" (2 words) -> "Hello world. This is"
             # If there are 3 sentences: S1. S2. S3(short). -> Show S2. S3.
             return "... " + sentences[-2] + " " + last_sentence

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
        # Acquire Lock (Serialization with Partial)
        with self.inference_lock:
             text = self.inference_service.transcribe(
                 audio_data,
                 language=config_manager.config.language if config_manager.config.language != "auto" else None,
                 initial_prompt=config_manager.config.initial_prompt
             )
        
        logger.info(f"Inference finished. Text: '{text}'")
        
        # Phase 15: AI Rewriting (Local LLM)
        if text and getattr(config_manager.config, "llm_enabled", False):
            self.ui_update_signal.emit("processing", "Refining text...")
            style = getattr(config_manager.config, "llm_style_preset", "Fix Grammar & Spelling")
            prompt = getattr(config_manager.config, "llm_custom_prompt", "")
            
            if style == "Fix Grammar & Spelling":
                prompt = "Fix grammar and spelling. Output ONLY the corrected text without any extra conversational text."
            elif style == "Professional Tone":
                prompt = "Rewrite to sound professional and polite. Output ONLY the rewritten text without any extra conversational text."
            elif style == "Casual Tone":
                prompt = "Rewrite to sound casual, friendly, and conversational. Output ONLY the rewritten text without any extra conversational text."
            elif style == "Concise Summary":
                prompt = "Summarize the text to be as concise as possible while retaining the core meaning. Output ONLY the summary without any extra conversational text."
            elif style == "Translate to English":
                prompt = "Translate the following text to English. Output ONLY the translation without any extra conversational text. If it is already in English, just fix grammar."

                
            model = getattr(config_manager.config, "llm_model", "")
            endpoint = getattr(config_manager.config, "llm_endpoint", "http://localhost:11434")
            
            refined_text = LLMClient.refine_text(text, prompt, endpoint, model)
            
            # If refinement triggered a fallback, text will be identical, or it might just happen to be the same
            if refined_text == text and prompt:
                 logger.warning("LLM refinement yielded same result or failed.")
                 # Optional: short warning beep. We'll play it on genuine errors detected by LLMClient natively,
                 # but here we can just do it if we suspect a hard fail (e.g., if there's no LLM). 
                 # Given LLMClient already falls back gracefully, we can trigger a soft error sound.
                 if not model:
                      sound.play_error_sound()
            
            text = refined_text

        if text:
            # Inject Text
            # We need to run this on main thread? 
            # pynput keyboard controller works from background threads usually.
            # But let's be safe. TextInjector seems safe.
            self.text_injector.inject_text(text)
        else:
            logger.info("Transcribed text is empty.")
            
        self.ui_update_signal.emit("idle", "Ready")
        self.preview_update_signal.emit("") # Clear preview

    def _on_panic(self):
        if self.is_recording:
            logger.info("Panic Button Pressed!")
            sound.play_cancel_sound()
            self.is_recording = False
            self.preview_timer.stop() # Stop preview
            self.audio_service.stop_capture() # Just to reset flags
            # self.audio_service.clear_buffer() # No need in new logic
            self.ui_update_signal.emit("idle", "Cancelled")
            self.preview_update_signal.emit("")

    def _on_model_loaded(self, success):
        """Callback from inference service."""
        if success:
            logger.info("Model loaded callback received.")
            self.ui_update_signal.emit("idle", "Ready")
            # Start Audio Listening now that model is ready
            self.audio_service.start_listening()
        else:
            self.ui_update_signal.emit("error", "Model Load Failed")
