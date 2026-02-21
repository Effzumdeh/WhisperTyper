from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QLineEdit, QCheckBox, QPlainTextEdit, QPushButton, QFormLayout, QWidget,
    QFrame, QApplication, QGroupBox, QMessageBox
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon, QKeySequence, QFont
import sounddevice as sd

from src.utils.config import config_manager
from src.ui.resources import Resources
from src.utils.hardware import HardwareManager
from src.core.llm_processor import LLMClient
from PySide6.QtWidgets import QGroupBox, QMessageBox

class HotkeyLineEdit(QLineEdit):
    """Custom QLineEdit to capture hotkeys."""
    hotkey_captured = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Press key combo...")
        self.current_sequence = None

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        
        if key == Qt.Key_Escape:
            self.clear()
            self.current_sequence = None
            return

        # Mapping modifiers
        parts = []
        if modifiers & Qt.ControlModifier: parts.append("<ctrl>")
        if modifiers & Qt.AltModifier: parts.append("<alt>")
        if modifiers & Qt.ShiftModifier: parts.append("<shift>")
        if modifiers & Qt.MetaModifier: parts.append("<cmd>")
        
        # Key
        if key not in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta):
            text = QKeySequence(key).toString().lower()
            parts.append(text)
            
        final = "+".join(parts)
        self.setText(final)
        self.current_sequence = final
        self.hotkey_captured.emit(final)


class SettingsDialog(QDialog):
    config_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WhisperTyper Settings")
        self.setWindowIcon(Resources.get_icon(Resources.ICON_TRAY))
        self.resize(550, 650)
        
        # Detect Hardware
        self.hw_profile = HardwareManager.get_profile()
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Header / Status
        self._init_header(layout)
        
        # Main Form
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        
        # Language
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["Auto", "en", "de", "fr", "es", "it", "pt", "nl", "ja", "zh", "ru"])
        self.combo_lang.setToolTip("Language of the speech. 'Auto' detects language but takes longer.")
        form_layout.addRow("Language:", self.combo_lang)
        
        # Model Size (Smart Selection)
        self.combo_model = QComboBox()
        self.combo_model.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self.combo_model.setToolTip("Select AI Model. \nTiny/Base: Fast, less accurate. \nMedium/Large: Accurate, slower.")
        form_layout.addRow("Model Accuracy:", self.combo_model)
        
        # Compute Device - Replaced by Force CPU Checkbox below (conditionally)
        # self.combo_compute_device = QComboBox() ... [REMOVED]
        
        # Microphone
        self.combo_device = QComboBox()
        form_layout.addRow("Microphone:", self.combo_device)
        
        # Hotkey
        self.line_hotkey = HotkeyLineEdit()
        self.line_hotkey.setToolTip("Click to record a new hotkey.")
        form_layout.addRow("Global Hotkey:", self.line_hotkey)
        
        layout.addLayout(form_layout)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # Checkboxes
        self.check_autostart = QCheckBox("Start with Windows")
        self.check_hallucination = QCheckBox("Smart Filtering (Remove 'Thanks for watching' etc.)")
        
        # Phase 14/15: Live Preview Dynamic Label
        preview_text = "Enable Live Preview"
        # Determine if we are likely on CPU or GPU
        is_gpu_available = (self.hw_profile.device_type == "cuda" or "HIP" in self.hw_profile.description)
        
        if is_gpu_available:
             preview_text += " (High GPU Usage)"
        else:
             preview_text += " (High CPU Usage)"
             
        self.check_live_preview = QCheckBox(preview_text)
        self.check_live_preview.setToolTip("Shows transcription while you speak. Requires more resources.")
        
        self.check_amd_hip = QCheckBox("Enable Experimental AMD HIP Support")
        self.check_amd_hip.setToolTip("Requires AMD HIP SDK installed. May cause instability. App will fallback to CPU if initialization fails.")
        
        # Debug / Troubleshooting
        self.check_debug = QCheckBox("Enable Debug Mode")
        self.check_debug.setToolTip("Sets log level to DEBUG in logs/whisper_typer.log and saves last recording to logs/last_recording.wav")
        
        layout.addWidget(self.check_autostart)
        layout.addWidget(self.check_hallucination)
        layout.addWidget(self.check_live_preview) 
        layout.addWidget(self.check_debug)
        
        # CPU Override (Conditionally Visible)
        # Show ONLY if we have a GPU (CUDA or HIP), so user can force it off.
        # If we are already CPU-only, this option is irrelevant.
        self.check_force_cpu = QCheckBox("Force CPU Mode")
        self.check_force_cpu.setToolTip("Disable GPU acceleration. Useful for troubleshooting hangs or high GPU load.")
        
        if is_gpu_available:
            layout.addWidget(self.check_force_cpu)
            self.check_force_cpu.setVisible(True)
        else:
            # We still create the object to avoid attribute errors, but hide it
            self.check_force_cpu.setVisible(False)
            # layout.addWidget(self.check_force_cpu) # Don't even add to layout if hidden? or add and hide?
            # Safer to add and hide so layout works? Or just don't add.
            # If I don't add to layout, it won't show.
            pass
            
        layout.addWidget(self.check_amd_hip)
        
        # Advanced / Vocab
        layout.addWidget(QLabel("Custom Vocabulary / Context:"))
        self.text_prompt = QPlainTextEdit()
        self.text_prompt.setPlaceholderText("Enter uncommon words, names, or technical terms here to improve accuracy...")
        self.text_prompt.setMaximumHeight(80)
        layout.addWidget(self.text_prompt)

        # Phase 15: AI Rewriting (Local LLM)
        self.group_llm = QGroupBox("AI Rewriting (Local LLM)")
        self.group_llm.setCheckable(True)
        self.group_llm.setChecked(False)
        self.group_llm.toggled.connect(self._on_llm_toggled)
        llm_layout = QFormLayout(self.group_llm)
        
        # Endpoint row
        endpoint_layout = QHBoxLayout()
        self.line_llm_endpoint = QLineEdit()
        self.line_llm_endpoint.setPlaceholderText("http://localhost:11434")
        self.btn_llm_test = QPushButton("Test Connection")
        self.btn_llm_test.clicked.connect(self._test_llm_connection)
        endpoint_layout.addWidget(self.line_llm_endpoint)
        endpoint_layout.addWidget(self.btn_llm_test)
        llm_layout.addRow("Endpoint URL:", endpoint_layout)
        
        # Model
        self.combo_llm_model = QComboBox()
        self.combo_llm_model.setEditable(True)
        llm_layout.addRow("LLM Model:", self.combo_llm_model)

        # Style
        self.combo_llm_style = QComboBox()
        self.combo_llm_style.addItems([
            "Fix Grammar & Spelling", 
            "Professional Tone", 
            "Casual Tone",
            "Concise Summary",
            "Translate to English",
            "Custom"
        ])
        self.combo_llm_style.currentTextChanged.connect(self._on_llm_style_changed)
        llm_layout.addRow("Rewrite Style:", self.combo_llm_style)
        
        # Custom Prompt
        self.text_llm_prompt = QPlainTextEdit()
        self.text_llm_prompt.setPlaceholderText("Enter custom system prompt for rewriting...")
        self.text_llm_prompt.setMaximumHeight(60)
        self.text_llm_prompt.setVisible(False)
        llm_layout.addRow("Custom Prompt:", self.text_llm_prompt)
        
        layout.addWidget(self.group_llm)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Settings")
        self.btn_save.setFixedHeight(35)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(35)
        
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        
        layout.addLayout(btn_layout)
        
        self._load_current_values()

    def _init_header(self, layout):
        # Hardware Status Card with Reset Button
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        status_layout = QVBoxLayout(status_frame)
        
        # Header Row
        header_row = QHBoxLayout()
        title = QLabel("System Status")
        title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        header_row.addWidget(title)
        header_row.addStretch()
        
        # Reset Button (Small)
        btn_reset = QPushButton("Reset Defaults")
        btn_reset.setToolTip("Reset all settings to factory defaults")
        btn_reset.setFixedWidth(100)
        btn_reset.setStyleSheet("""
            QPushButton {
                 font-size: 11px;
                 padding: 2px;
                 color: #555;
            }
            QPushButton:hover {
                color: #d00;
                background-color: #fee;
            }
        """)
        btn_reset.clicked.connect(self.reset_settings)
        header_row.addWidget(btn_reset)
        
        status_layout.addLayout(header_row)
        
        status_text = f"Hardware: {self.hw_profile.description}"
        if self.hw_profile.device_type == "cuda":
            status_text += f" - GPU Acceleration Active ({self.hw_profile.recommended_compute})"
        elif "AMD" in self.hw_profile.description:
             status_text += " - No ROCm Execution Support (CPU Fallback)"
        else:
            status_text += " - CPU Mode (Slower)"
            
        status = QLabel(status_text)
        if self.hw_profile.device_type == "cuda":
             status.setStyleSheet("color: #00AA00; font-weight: bold;")
        elif "AMD" in self.hw_profile.description:
             status.setStyleSheet("color: #CC7700; font-weight: bold;") 
        else:
             status.setStyleSheet("color: #666666;")
             
        status_layout.addWidget(status)
        layout.addWidget(status_frame)

    def _on_llm_toggled(self, checked: bool):
        pass

    def _test_llm_connection(self):
        endpoint = self.line_llm_endpoint.text().strip()
        if not endpoint:
            QMessageBox.warning(self, "Warning", "Please enter an endpoint URL.")
            return
            
        self.btn_llm_test.setEnabled(False)
        self.btn_llm_test.setText("Testing...")
        QApplication.processEvents()
        
        models = LLMClient.fetch_ollama_models(endpoint)
        
        self.btn_llm_test.setEnabled(True)
        self.btn_llm_test.setText("Test Connection")
        
        if models:
            self.combo_llm_model.clear()
            self.combo_llm_model.addItems(models)
            QMessageBox.information(self, "Success", f"Found {len(models)} models.")
        else:
            QMessageBox.critical(self, "Error", "Could not fetch models. Check endpoint or Ollama status.")

    def _on_llm_style_changed(self, text: str):
        self.text_llm_prompt.setVisible(text == "Custom")

    def showEvent(self, event):
        """Refresh devices when dialog opens."""
        self._refresh_audio_devices()
        super().showEvent(event)

    def _refresh_audio_devices(self):
        self.combo_device.clear()
        self.combo_device.addItem("Default System Device", None)
        
        try:
            import re
            devices = sd.query_devices()
            current_id = config_manager.config.input_device_id
            default_index = 0
            
            # 1. Find WASAPI Host API Index
            wasapi_index = -1
            host_apis = sd.query_hostapis()
            for i, api in enumerate(host_apis):
                if "WASAPI" in api['name']:
                    wasapi_index = i
                    break
            
            black_list = ["Mapper", "Stereo Mix", "Hands-Free", "Line In", "Output", "Speaker"]
            
            clean_devices = []

            for i, dev in enumerate(devices):
                # Rule 1: Channels > 0
                if dev['max_input_channels'] <= 0:
                    continue
                
                # Rule 2: Strict WASAPI (if available on system)
                if wasapi_index != -1 and dev['hostapi'] != wasapi_index:
                    continue
                    
                raw_name = dev['name']
                
                # Rule 3: Blacklist
                if any(bad in raw_name for bad in black_list):
                    continue
                    
                # Rule 4: Sanitize Name via Regex
                # Remove Windows internal driver paths like (@System32...)
                clean_name = re.sub(r'\( @System32.*?\)', '', raw_name)
                
                # Remove common driver duplication like " (Realtek High Definition Audio)"
                # Regex: Space + Paren + Any + Audio + Paren at end of string
                clean_name = re.sub(r'\s*\(.*?Audio\)$', '', clean_name)
                
                clean_name = clean_name.strip()
                
                clean_devices.append((clean_name, i))
            
            # Sort alphabetically for cleanliness
            clean_devices.sort(key=lambda x: x[0])
            
            for name, i in clean_devices:
                self.combo_device.addItem(name, i)
                if current_id == i:
                     default_index = self.combo_device.count() - 1

            self.combo_device.setCurrentIndex(default_index)
            
        except Exception as e:
             self.combo_device.addItem(f"Error: {e}")

    def reset_settings(self):
        """Reset to defaults and refresh UI."""
        # Optional: Confirm dialog
        # For now, immediate.
        
        cfg = config_manager.reset_to_defaults()
        
        # Reload UI from new cfg
        self._load_current_values()
        
        # Trigger updates
        self.config_changed.emit()

    def _load_current_values(self):
        # ... (rest of method same)
        cfg = config_manager.config
        
        # Lang
        idx = self.combo_lang.findText(cfg.language if cfg.language != "auto" else "Auto", Qt.MatchFixedString)
        if idx >= 0: self.combo_lang.setCurrentIndex(idx)
        else: self.combo_lang.setCurrentIndex(0)
        
        # But config has "base" default. 
        # If hardware recommends "large", we should probably show "large" if config matches recommended?
        # Or just show config.
        
        # Device Mapping
        # If force_cpu is True, check the box.
        self.check_force_cpu.setChecked(getattr(cfg, "force_cpu", False))

        idx = self.combo_model.findText(cfg.model_size)
        # Phase 6: "Default to recommended_model" from HardwareManager
        # We did this in init sort of.
        
        idx = self.combo_model.findText(cfg.model_size)
        if idx >= 0: 
            self.combo_model.setCurrentIndex(idx)
        else:
             # Fallback
             pass
        
        # Hotkey
        self.line_hotkey.setText(cfg.hotkey)
        
        # Booleans
        self.check_autostart.setChecked(cfg.autostart)
        self.check_hallucination.setChecked(cfg.hallucination_filter)
        self.check_amd_hip.setChecked(getattr(cfg, "enable_amd_hip", False))
        
        # Preview
        self.check_live_preview.setChecked(getattr(cfg, 'live_preview', False))
        
        # Debug
        self.check_debug.setChecked(getattr(cfg, 'debug_mode', False))
        
        # Prompt
        if cfg.initial_prompt:
            self.text_prompt.setPlainText(cfg.initial_prompt)
        else:
            self.text_prompt.clear()
            
        # LLM Rewriting
        self.group_llm.setChecked(getattr(cfg, "llm_enabled", False))
        self.line_llm_endpoint.setText(getattr(cfg, "llm_endpoint", "http://localhost:11434"))
        
        saved_model = getattr(cfg, "llm_model", "")
        if saved_model:
            self.combo_llm_model.addItem(saved_model)
            self.combo_llm_model.setCurrentText(saved_model)
            
        saved_style = getattr(cfg, "llm_style_preset", "Fix Grammar & Spelling")
        idx = self.combo_llm_style.findText(saved_style)
        if idx >= 0:
            self.combo_llm_style.setCurrentIndex(idx)
            
        self.text_llm_prompt.setPlainText(getattr(cfg, "llm_custom_prompt", ""))
        self.text_llm_prompt.setVisible(saved_style == "Custom")

    def save_settings(self):
        cfg = config_manager.config
        
        # Lang
        lang = self.combo_lang.currentText()
        cfg.language = lang if lang != "Auto" else "auto"
        
        # Model
        cfg.model_size = self.combo_model.currentText()
        # Compute type is now AUTOMATIC via inference service, we don't save it from UI.
        # But we still store it in config for consistency?
        # Actually inference service should ignore config.compute_type OR we update it here using HardwareManager?
        # Let's update it here so it's persisted correctly.
        cfg.compute_type = HardwareManager.get_compute_type(cfg.model_size)
        
        # Hotkey
        if self.line_hotkey.text():
            cfg.hotkey = self.line_hotkey.text()
            
        # Device
        device_id = self.combo_device.currentData()
        cfg.input_device_id = device_id
        if self.combo_device.currentIndex() > 0:
             try:
                 cfg.input_device_name = self.combo_device.currentText()
             except: pass
        else:
             cfg.input_device_name = "Default"
             
        # Booleans
        cfg.autostart = self.check_autostart.isChecked()
        cfg.hallucination_filter = self.check_hallucination.isChecked()
        cfg.enable_amd_hip = self.check_amd_hip.isChecked()
        cfg.live_preview = self.check_live_preview.isChecked()
        
        # Debug
        old_debug = getattr(cfg, "debug_mode", False)
        new_debug = self.check_debug.isChecked()
        cfg.debug_mode = new_debug
        
        if old_debug != new_debug:
             from src.utils.logger import update_logging_level
             update_logging_level(new_debug)
             
        # Device / Force CPU
        cfg.force_cpu = self.check_force_cpu.isChecked()
        cfg.device_id = 0 # Always 0 for now
        
        # Prompt
        prompt = self.text_prompt.toPlainText().strip()
        cfg.initial_prompt = prompt if prompt else None
        
        # LLM
        cfg.llm_enabled = self.group_llm.isChecked()
        cfg.llm_endpoint = self.line_llm_endpoint.text().strip()
        cfg.llm_model = self.combo_llm_model.currentText().strip()
        cfg.llm_style_preset = self.combo_llm_style.currentText()
        cfg.llm_custom_prompt = self.text_llm_prompt.toPlainText().strip()
        
        config_manager.save_config()
        self.accept()
        self.config_changed.emit()
