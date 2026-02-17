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
                    # Auto-determine compute type to ensure safety and performance
                    compute_type = HardwareManager.get_compute_type(model_size)
                    
                    logger.info(f"Selected compute type: {compute_type} for model: {model_size}")
                    
                    # Check for cached model in our portable/appdata dir
                    download_root = str(config_manager.paths.models_dir)
                    
                    # 2. Offline / Cached Loading Strategy
                    # Try loading offline first to avoid Hugging Face API checks (speed + privacy)
                    try:
                        logger.info(f"Attempting to load {model_size} from local cache...")
                        self.model = WhisperModel(
                            model_size, 
                            device="auto", # auto-detect CUDA/CPU
                            compute_type=compute_type,
                            download_root=download_root,
                            local_files_only=True
                        )
                        logger.info(f"Successfully loaded '{model_size}' from local cache.")
                    except Exception as e:
                        logger.info(f"Local load failed ({e}). Proceeding to download/online check...")
                        self.model = WhisperModel(
                            model_size, 
                            device="auto", 
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
            return ""
            
        try:
            # Normalize audio if volume is low
            # Whisper works best with normalized audio (-1 to 1)
            # If max amplitude is very low (e.g. < 0.1), boost it.
            max_amp = np.max(np.abs(audio_data))
            if max_amp > 0 and max_amp < 0.5:
                # Scale to target peak of 0.9
                scaling_factor = 0.9 / max_amp
                audio_data = audio_data * scaling_factor
                logger.info(f"Audio normalized. scaling_factor: {scaling_factor:.2f}, new max: {np.max(np.abs(audio_data)):.2f}")
            
            # Use explicit args or config defaults
            # Note: config default for language might be "auto" -> None
            if language is None:
                config_lang = config_manager.config.language
                language = config_lang if config_lang != "auto" else None
                
            if initial_prompt is None:
                initial_prompt = config_manager.config.initial_prompt

            logger.info(f"Transcribing... Language: {language}, Task: transcribe")

            segments, info = self.model.transcribe(
                audio_data,
                beam_size=5,
                language=language,
                task="transcribe", # FORCE TRANSCRIBE (No translation)
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
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

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
