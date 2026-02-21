import os
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from platformdirs import user_config_dir, user_data_dir, user_cache_dir

class AppConfig(BaseModel):
    """Application configuration model."""
    language: str = "en"
    model_size: str = "base"
    compute_type: str = "int8"
    hotkey: str = "<ctrl>+<alt>+s"
    initial_prompt: Optional[str] = None
    hallucination_filter: bool = True
    
    # Phase 14: Live Preview
    live_preview: bool = True

    # Phase 15: AI Rewriting (Local LLM)
    llm_enabled: bool = False
    llm_endpoint: str = "http://localhost:11434"
    llm_model: str = ""
    llm_style_preset: str = "Fix Grammar & Spelling"
    llm_custom_prompt: str = ""

    # Debug / Troubleshooting
    debug_mode: bool = False
    force_cpu: bool = False
    device_id: int = 0 # 0=Auto, 1=GPU0, 2=GPU1 etc. (Implementation specific mapping)
    
    # Experimental
    enable_amd_hip: bool = False
    
    # Audio settings
    input_device_id: Optional[int] = None
    input_device_name: Optional[str] = None
    energy_threshold: int = 1000
    autostart: bool = False
    
class PathManager:
    """Manages application paths for portable and installed modes."""
    
    def __init__(self):
        self.is_portable = self._detect_portable()
        self.app_name = "WhisperTyper"
        self.app_author = "Effzumdeh" # Updated from Florian
        
        if self.is_portable:
            base_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(os.getcwd())
            self.data_dir = base_dir / "data"
            self.config_dir = self.data_dir / "config"
            self.cache_dir = self.data_dir / "cache"
            self.models_dir = self.data_dir / "models"
        else:
            self.data_dir = Path(user_data_dir(self.app_name, self.app_author))
            self.config_dir = Path(user_config_dir(self.app_name, self.app_author))
            self.cache_dir = Path(user_cache_dir(self.app_name, self.app_author))
            self.models_dir = self.cache_dir / "models"
            
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
    def _detect_portable(self) -> bool:
        """Check for .portable marker file."""
        if getattr(sys, 'frozen', False):
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(os.getcwd())
            
        return (base_path / ".portable").exists()
    
    def get_config_path(self) -> Path:
        return self.config_dir / "config.json"
        
class ConfigManager:
    """Singleton for managing app configuration."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.paths = PathManager()
            cls._instance.config = cls._instance._load_config()
        return cls._instance
        
    def _load_config(self) -> AppConfig:
        config_path = self.paths.get_config_path()
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return AppConfig.model_validate_json(f.read())
            except Exception as e:
                print(f"Error loading config: {e}. Using defaults.")
                return self._create_default_config()
        return self._create_default_config()

    def _create_default_config(self) -> AppConfig:
        return AppConfig(language=self._detect_system_language())

    def _detect_system_language(self) -> str:
        try:
            import locale
            # getloadale() is sometimes problematic on Windows, getdefaultlocale is safer for this purpose
            loc = locale.getdefaultlocale()
            if loc and loc[0]:
                lang_code = loc[0].split('_')[0].lower() # 'de'
                # Supported languages in our UI
                supported = ["en", "de", "fr", "es", "it", "pt", "nl", "ja", "zh", "ru"]
                if lang_code in supported:
                    return lang_code
        except Exception:
            pass
        return "auto" # Fallback if unknown or detection fails
        
    def save_config(self):
        config_path = self.paths.get_config_path()
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(self.config.model_dump_json(indent=4))

    def reset_to_defaults(self) -> AppConfig:
        """Resets configuration to factory defaults and saves it."""
        self.config = self._create_default_config()
        # Update hotkey to new standard per Phase 6.1
        self.config.hotkey = "<ctrl>+<alt>+<shift>+s"
        self.save_config()
        return self.config

# Global instance
config_manager = ConfigManager()
