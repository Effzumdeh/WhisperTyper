import logging
import platform
import shutil
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import ctranslate2 for CUDA check
try:
    import ctranslate2
    HAS_CTRANSLATE2 = True
except ImportError:
    HAS_CTRANSLATE2 = False
    
# Try to import torch for VRAM check (if available in environment)
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

@dataclass
class DeviceProfile:
    device_type: str # "cuda" or "cpu"
    vram_gb: float # 0 if CPU or unknown
    recommended_model: str
    recommended_compute: str
    description: str

class HardwareManager:
    @staticmethod
    def get_profile() -> DeviceProfile:
        device_type = "cpu"
        vram_gb = 0.0
        
        # 1. Check CUDA availability (Primary target for faster-whisper/ctranslate2)
        cuda_available = False
        if HAS_CTRANSLATE2:
            try:
                count = ctranslate2.get_cuda_device_count()
                if count > 0:
                    cuda_available = True
                    device_type = "cuda"
            except Exception as e:
                logger.warning(f"Error checking CUDA devices via ctranslate2: {e}")
                
        # 2. Check VRAM if CUDA is available
        if cuda_available:
            if HAS_TORCH:
                try:
                    if torch.cuda.is_available():
                        vram_bytes = torch.cuda.get_device_properties(0).total_memory
                        vram_gb = vram_bytes / (1024**3)
                except Exception as e:
                    logger.warning(f"Error getting VRAM via torch: {e}")
            
            # Fallback VRAM if torch failed or not present
            if vram_gb == 0.0:
                 vram_gb = 4.0 # Assume 4GB safe default for CUDA
                 
            return HardwareManager._recommend(device_type, vram_gb)

        # 3. Check for AMD / Other GPU via WMI (Windows)
        # If we are strictly CPU so far, check if we can see a GPU in WMI to acknowledge presence
        if device_type == "cpu" and platform.system() == "Windows":
             try:
                 import wmi
                 w = wmi.WMI()
                 for video in w.Win32_VideoController():
                     name = video.Name
                     # Check for AMD/NVIDIA
                     if "AMD" in name or "Radeon" in name:
                          return DeviceProfile(
                              device_type="cpu", 
                              vram_gb=0, 
                              recommended_model="small", 
                              recommended_compute="int8", 
                              description=f"Detected: {name} - (No ROCm/CUDA -> Using CPU Mode)"
                          )
                     elif "NVIDIA" in name:
                          # This implies we failed to detect it via ctranslate2/torch
                          return DeviceProfile(
                              device_type="cpu", 
                              vram_gb=0, 
                              recommended_model="small", 
                              recommended_compute="int8", 
                              description=f"Detected: {name} - (Driver Issue -> Using CPU Mode)"
                          )
             except Exception as e:
                 logger.warning(f"WMI check failed: {e}")

        return HardwareManager._recommend("cpu", 0.0)

    @staticmethod
    def _recommend(device_type: str, vram_gb: float) -> DeviceProfile:
        # ... existing logic ...
        rec_model = "base"
        rec_compute = "int8"
        description = "Standard CPU (No Acceleration)"
        
        if device_type == "cuda":
            if vram_gb > 8.0:
                rec_model = "large-v3"
                rec_compute = "float16"
                description = f"NVIDIA GPU ({vram_gb:.1f} GB VRAM)"
            elif vram_gb > 4.0:
                rec_model = "medium"
                rec_compute = "float16"
                description = f"NVIDIA GPU ({vram_gb:.1f} GB VRAM)"
            elif vram_gb > 2.0:
                rec_model = "small"
                rec_compute = "int8"
                description = f"NVIDIA GPU ({vram_gb:.1f} GB VRAM)"
            else:
                rec_model = "tiny"
                rec_compute = "int8" 
                description = f"NVIDIA GPU ({vram_gb:.1f} GB VRAM)"
        
        return DeviceProfile(device_type, vram_gb, rec_model, rec_compute, description)

    @staticmethod
    def get_compute_type(model_size: str) -> str:
        """
        Determines the best compute type for a given model and device.
        Automagically called by inference service.
        """
        profile = HardwareManager.get_profile()
        
        if profile.device_type == "cpu":
            return "int8"
            
        # CUDA Logic
        # If model is large, and we have low VRAM, force int8?
        if model_size == "large-v3" and profile.vram_gb > 0 and profile.vram_gb < 8.0:
            return "int8"
            
        return "float16" # Default for valid CUDA usage
