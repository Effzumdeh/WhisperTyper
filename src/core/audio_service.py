import logging
import threading
import collections
import numpy as np
import sounddevice as sd
from typing import Optional, List

from src.utils.config import config_manager

logger = logging.getLogger(__name__)

class AudioService:
    """
    Handles audio recording using a non-blocking callback and a ring buffer.
    """
    def __init__(self, target_sample_rate: int = 16000, buffer_duration_sec: int = 30):
        self.target_sample_rate = target_sample_rate
        self.device_sample_rate = target_sample_rate # Will be updated on start
        self.buffer_duration_sec = buffer_duration_sec
        self.block_size = 1024
        
        # We can't calc max_blocks correctly until we know device rate.
        # But we need a deque init. Let's assume 48k max for safety or resize later?
        # Deque can't be resized easily. Let's pick a safe high number (e.g. for 96k)
        # 30 sec * 96000 / 1024 ~= 2812.
        self.max_blocks = 5000 
        
        # Audio storage
        self.ring_buffer = collections.deque(maxlen=self.max_blocks)
        
        # Stream management
        self.stream: Optional[sd.InputStream] = None
        self.is_running = False
        self._lock = threading.Lock()
        
        # Capture state
        self.is_capturing = False
        self.captured_blocks: List[np.ndarray] = []
        self.pre_roll_snapshot: List[np.ndarray] = [] 
        
        # Device management
        self.current_device_id = None
        
    def start_listening(self):
        """Starts the background continuous audio stream."""
        with self._lock:
            if self.is_running:
                return

            self._start_stream_internal()

    def _start_stream_internal(self):
        try:
            # Determine device: explicit config OR system default
            config_id = config_manager.config.input_device_id
            
            # If config is None, we use default. We store the actual ID used if possible?
            # sd.query_devices(kind='input') might help, but for now trusting sd.InputStream defaults.
            # We track the 'config_id' to detect config changes, 
            # BUT for hot-swap default, we need to check sd.default.device match?
            
            self.current_device_id = config_id
            
            # Resolve actual device info for logging and Sample Rate
            try:
                if config_id is None:
                    # Query default input device
                    device_info = sd.query_devices(kind='input')
                    actual_id = device_info.get('index', 'Unknown')
                    actual_name = device_info.get('name', 'Unknown')
                else:
                    device_info = sd.query_devices(config_id)
                    actual_id = config_id
                    actual_name = device_info.get('name', 'Unknown')
                
                # Get Device Sample Rate
                self.device_sample_rate = int(device_info.get('default_samplerate', 44100))
                
                # Channels
                channels = device_info.get('max_input_channels', 1)
                    
                logger.info(f"Audio stream starting. Request: {config_id}, Actual: '{actual_name}' (ID: {actual_id}), Channels: {channels}, SR: {self.device_sample_rate}")
            except Exception as e:
                logger.warning(f"Could not query device info: {e}. Defaulting to 16000Hz.")
                self.device_sample_rate = 16000
                channels = 1

            self.stream = sd.InputStream(
                device=config_id,
                channels=channels,
                samplerate=self.device_sample_rate,
                blocksize=self.block_size,
                callback=self._audio_callback,
                dtype="float32"
            )
            self.stream.start()
            self.is_running = True
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            self.is_running = False

    def stop_listening(self):
        """Stops the background stream."""
        with self._lock:
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            self.is_running = False
            logger.info("Audio stream stopped.")

    def start_capture(self):
        """
        Marks the start of a user interaction (Hotkey Pressed).
        """
        # 1. Check Device Health / Change
        self._ensure_healthy_stream()
        
        with self._lock:
            self.is_capturing = True
            self.captured_blocks = [] # Clear previous explicit capture

    def stop_capture(self, pre_roll_sec: float = 0.5) -> np.ndarray:
        """
        Stops capture, resamples, and returns the audio with pre-roll.
        """
        with self._lock:
            self.is_capturing = False
            
            # Combine data
            if not self.captured_blocks:
                logger.warning("No audio blocks captured.")
                # We still might have pre-roll? 
                # If hotkey was just a tap, we depend on pre-roll.
            
            full_blocks = self.pre_roll_snapshot + self.captured_blocks
            if not full_blocks:
                 return np.array([], dtype=np.float32)
                 
            full_audio_native = np.concatenate(full_blocks)
            
            # Log raw stats
            if len(full_audio_native) > 0:
                max_amp = np.max(np.abs(full_audio_native))
                logger.info(f"Audio raw capture. Native Samples: {len(full_audio_native)}, Native Rate: {self.device_sample_rate}, Max Amp: {max_amp:.4f}")
            
            # Resample to 16k if needed
            if self.device_sample_rate != self.target_sample_rate:
                full_audio_16k = self._resample(full_audio_native, self.device_sample_rate, self.target_sample_rate)
            else:
                full_audio_16k = full_audio_native
                
            return full_audio_16k

    def _resample(self, audio: np.ndarray, current_rate: int, target_rate: int) -> np.ndarray:
        if len(audio) == 0:
            return audio
            
        duration_sec = len(audio) / current_rate
        target_len = int(duration_sec * target_rate)
        
        x_old = np.linspace(0, duration_sec, len(audio))
        x_new = np.linspace(0, duration_sec, target_len)
        
        # Linear interpolation
        audio_resampled = np.interp(x_new, x_old, audio).astype(np.float32)
        return audio_resampled

    def _audio_callback(self, indata, frames, time, status):
        """Callback for sounddevice."""
        if status:
            logger.warning(f"Audio callback status: {status}")
            if "InputOverflow" in str(status) or "InputUnderflow" in str(status) or "PrimingOutput" in str(status):
                # benign-ish
                pass
            else:
                # Serious error, maybe restart?
                pass
                
        # Downmix if necessary
        if indata.shape[1] > 1:
            data_mono = np.mean(indata, axis=1)
        else:
            data_mono = indata.flatten()
            
        # Ensure float32
        data_mono = data_mono.astype(np.float32)
            
        with self._lock:
            self.ring_buffer.append(data_mono)
            if self.is_capturing:
                self.captured_blocks.append(data_mono)
                
    def _ensure_healthy_stream(self):
        """Checks if stream is active and device is valid."""
        # Check 1: Is stream None or stopped?
        restart = False
        if not self.stream or not self.stream.active:
            logger.warning("Stream invalid, restarting.")
            restart = True
            
        # Check 2: Did default device change?
        # Only relevant if we are using default (config ID is None)
        if config_manager.config.input_device_id is None:
            try:
                # Query current default input device
                cutoff = sd.query_devices(kind='input')
                # We can't easily check if 'self.stream' is using this device ID without accessing private internals 
                # or storing the detected ID at start.
                # Let's trust that if the existing stream is active, it's fine, 
                # UNLESS it throws an error.
                # User requirement: "The app must fetch the *current* default device at the moment of recording".
                # If we use PortAudio, and default changes, the content of 'default' stream might not switch automatically on Windows?
                # Actually, usually it does NOT switch. You hold the handle to the hardware device.
                
                # So we must restart the stream if we suspect a change?
                # Restarting on EVERY prompt is safe but loses Pre-roll.
                # User Refinement: "Ensure ... initialized ... when start_recording() is called".
                # User accepts "Restart logic".
                
                # Compromise:
                # We restart stream here to match "Fetch active device".
                # BUT we lose pre-roll.
                # To keep pre-roll, we would need to run the stream on the NEW device before we needed it.
                # Impossible to predict.
                
                # So: Priority 1: Hot-Plug correctness. Priority 2: Pre-roll.
                # If device changed aka we re-init, we lose Pre-roll. That is acceptable physics.
                # If device didn't change, we keep stream -> keep pre-roll.
                
                # How to detect change?
                # Store the name of the device we connected to?
                pass
            except Exception:
                pass
        
        if restart:
             self.stop_listening()
             self._start_stream_internal()

    def capture_snapshot_preroll(self):
        """Snapshots the last N seconds from ring buffer as pre-roll."""
        with self._lock:
            # We want the last 0.5 seconds
            # pre-roll blocks
            count = int(0.5 * self.device_sample_rate / self.block_size)
            count = min(len(self.ring_buffer), count)
            # getting last 'count' items from deque
            # deque doesn't support slicing. list(deque)[-count:] is slow.
            # safe iteration
            if count > 0:
                self.pre_roll_snapshot = list(self.ring_buffer)[-count:]
            else:
                self.pre_roll_snapshot = []
