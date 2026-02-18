import logging
import re
import threading
import queue
import gc
from typing import Optional, Callable
import numpy as np
from faster_whisper import WhisperModel

from src.utils.config import config_manager

from src.utils.hardware import HardwareManager

logger = logging.getLogger(__name__)

class InferenceService:
    """
    Handles audio transcription using faster-whisper.
    """
    def __init__(self):
        self.model: Optional[WhisperModel] = None
        self.model_path: Optional[str] = None
        self._load_lock = threading.Lock()
        
    def load_model(self, on_complete: Optional[Callable[[bool], None]] = None):
        """
        Loads the Whisper model in a background thread.
        
        Args:
            on_complete: Callback function (success: bool) -> None
        """
        def _load():
            with self._load_lock:
                try:
                    logger.info("Loading Whisper model...")
                    
                    # 1. Memory Cleanup
                    if self.model is not None:
                        logger.info("Unloading previous model...")
                        del self.model
                        self.model = None
                        gc.collect()
                        # Explicitly empty CUDA cache if torch is available
                        try:
                            import torch
                            if torch.cuda.is_available():
                                torch.cuda.empty_cache()
                        except ImportError:
                            pass
                        logger.info("Memory cleared for model reload.")
                    
                    # Resolve paths
                    model_size = config_manager.config.model_size

                    # Hardware Profile
                    profile = HardwareManager.get_profile()
                    force_cpu = config_manager.config.force_cpu
                    
                    # Compute Type & Device Logic
                    device = "auto"
                    compute_type = config_manager.config.compute_type 
                    
                    if force_cpu:
                        logger.info("Force CPU Mode enabled. Ignoring GPU.")
                        device = "cpu"
                        compute_type = "int8"
                    elif profile.device_type == "cuda":
                        device = "cuda"
                        # Smart Defaults for Nvidia
                        if profile.is_nvidia and profile.vram_gb > 0 and profile.vram_gb < 4.0:
                             logger.info(f"Low VRAM detected ({profile.vram_gb:.1f} GB). Forcing int8.")
                             compute_type = "int8"
                        else:
                             compute_type = HardwareManager.get_compute_type(model_size)
                    
                    logger.info(f"Loading Model: {model_size}, Device: {device}, Compute: {compute_type}")
                    
                    download_root = str(config_manager.paths.models_dir)
                    
                    # --- Experimental AMD HIP Handling ---
                    use_hip = getattr(config_manager.config, "enable_amd_hip", False)
                    hip_loaded = False
                    
                    if use_hip and HardwareManager.is_hip_available():
                        try:
                            logger.info("AMD HIP Support Enabled. Attempting to initialize...")
                            # 1. DLL Injection
                            hip_path = HardwareManager._get_hip_sdk_path()
                            if hip_path:
                                import os
                                bin_path = os.path.join(hip_path, "bin")
                                if os.path.isdir(bin_path):
                                    # Specific to Windows Python 3.8+
                                    if hasattr(os, "add_dll_directory"):
                                        os.add_dll_directory(bin_path)
                                        logger.info(f"Added DLL directory: {bin_path}")
                                    else:
                                        # Fallback for older python or non-windows? (Unlikely here)
                                        os.environ["PATH"] = bin_path + os.pathsep + os.environ["PATH"]
                            
                            # 2. Attempt Load
                            logger.info(f"Loading {model_size} on device='cuda' (HIP backend)...")
                            self.model = WhisperModel(
                                model_size,
                                device="cuda",
                                compute_type="float16", # HIP usually handles float16
                                download_root=download_root
                            )
                            logger.info("Successfully loaded model with AMD HIP acceleration.")
                            hip_loaded = True
                        except Exception as e:
                            logger.error(f"AMD HIP Initialization Failed: {e}")
                            if "insufficient" in str(e) or "CUDA" in str(e):
                                logger.error("Hint: This version of 'ctranslate2' seems to be compiled for NVIDIA CUDA. AMD HIP support on Windows currently requires compiling 'ctranslate2' from source with '-DWITH_HIP=ON'.")
                            
                            logger.warning("Falling back to standard CPU/Auto mode.")
                            self.model = None
                            # Fall through to standard logic
                    
                    if hip_loaded:
                         if on_complete: on_complete(True)
                         return

                    # --- Standard Loading Strategy (CPU/CUDA-Native) ---
                    # Check for cached model in our portable/appdata dir
                    
                    # 2. Offline / Cached Loading Strategy
                    # Try loading offline first to avoid Hugging Face API checks (speed + privacy)
                    try:
                        logger.info(f"Attempting to load {model_size} from local cache...")
                        self.model = WhisperModel(
                            model_size, 
                            device=device, 
                            compute_type=compute_type,
                            download_root=download_root,
                            local_files_only=True
                        )
                        logger.info(f"Successfully loaded '{model_size}' from local cache.")
                    except Exception as e:
                        logger.info(f"Local load failed ({e}). Proceeding to download/online check...")
                        self.model = WhisperModel(
                            model_size, 
                            device=device, 
                            compute_type=compute_type,
                            download_root=download_root,
                            local_files_only=False
                        )
                        logger.info(f"Successfully downloaded and loaded '{model_size}'.")
                        
                    if on_complete:
                        on_complete(True)
                except Exception as e:
                    logger.error(f"Failed to load Whisper model: {e}")
                    if on_complete:
                        on_complete(False)

        threading.Thread(target=_load, daemon=True).start()

    def transcribe(self, audio_data: np.ndarray, language: Optional[str] = None, initial_prompt: Optional[str] = None) -> str:
        """
        Transcribes the given audio data.
        
        Args:
            audio_data: Numpy array of shape (N,) or (N, 1), float32.
            language: Language code (e.g. "en", "de") or None for auto.
            initial_prompt: Context string for Whisper.
            
        Returns:
            The transcribed text.
        """
        if self.model is None:
            logger.error("Model not loaded.")
            raise RuntimeError("Model not loaded")
            
        # Normalize audio if volume is low
        max_amp = np.max(np.abs(audio_data))
        if max_amp > 0 and max_amp < 0.5:
            scaling_factor = 0.9 / max_amp
            audio_data = audio_data * scaling_factor
        
        if language is None:
            config_lang = config_manager.config.language
            language = config_lang if config_lang != "auto" else None
            
        if initial_prompt is None:
            initial_prompt = config_manager.config.initial_prompt

        logger.info(f"Transcribing... Language: {language}, Task: transcribe")

        # No try/except here - let it propagate to Worker
        segments, info = self.model.transcribe(
            audio_data,
            beam_size=5,
            language=language,
            task="transcribe",
            initial_prompt=initial_prompt,
            condition_on_previous_text=False
        )
        
        text_segments = []
        for segment in segments:
            text_segments.append(segment.text)
            
        full_text = " ".join(text_segments).strip()
        
        # Hallucination Filter
        if config_manager.config.hallucination_filter:
            full_text = self._filter_hallucinations(full_text)
            
        return full_text

    def _filter_hallucinations(self, text: str) -> str:
        """
        Removes common Whisper hallucinations.
        """
        # Common hallucinated phrases (can be extended)
        hallucinations = [
            r"Thanks for watching",
            r"Subscribe to my channel",
            r"Untertitel der im Auftrag", # German specific
            r"Amara.org"
        ]
        
        filtered_text = text
        for pattern in hallucinations:
            # Case insensitive remove
            filtered_text = re.sub(pattern, "", filtered_text, flags=re.IGNORECASE)
            
        # Clean up double spaces or empty punctuation
        filtered_text = re.sub(r'\s+', ' ', filtered_text).strip()
        
        return filtered_text
