import os
import logging
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import pynvml for robust NV detection
try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False

# Try to import ctranslate2 for CUDA check
try:
    import ctranslate2
    HAS_CTRANSLATE2 = True
except ImportError:
    HAS_CTRANSLATE2 = False

# Try to import torch for VRAM check fallback
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
    is_nvidia: bool = False

class HardwareManager:
    @staticmethod
    def _get_hip_sdk_path() -> str | None:
        """Returns the path to the HIP SDK if feasible, or None."""
        # 1. Common env vars for HIP/ROCm on Windows
        candidates = ["HIP_PATH", "AMD_HIP_PATH", "ROCM_PATH"]
        for env in candidates:
             val = os.environ.get(env)
             if val and os.path.isdir(val):
                 return val
        
        # 2. Check default install location: C:\Program Files\AMD\ROCm\*\bin
        try:
            default_root = Path(r"C:\Program Files\AMD\ROCm")
            if default_root.exists():
                versions = [p for p in default_root.iterdir() if p.is_dir()]
                if versions:
                    versions.sort(key=lambda p: p.name)
                    latest = versions[-1]
                    if (latest / "bin").exists():
                        return str(latest)
        except Exception as e:
            logger.warning(f"Error checking default HIP paths: {e}")

        return None

    @staticmethod
    def is_hip_available() -> bool:
        return HardwareManager._get_hip_sdk_path() is not None

    @staticmethod
    def get_profile() -> DeviceProfile:
        device_type = "cpu"
        vram_gb = 0.0
        description = "Standard CPU (No Acceleration)"
        is_nvidia = False
        
        # 0. Check NVML first for authoritative Nvidia info (even if CUDA is broken in torch/ctranslate2)
        if HAS_PYNVML:
            try:
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                name_bytes = pynvml.nvmlDeviceGetName(handle)
                # Decode bytes to string if needed (pynvml returns bytes in older, str in newer? usually bytes)
                if isinstance(name_bytes, bytes):
                    name = name_bytes.decode("utf-8")
                else:
                    name = str(name_bytes)
                    
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                vram_gb = mem_info.total / (1024**3)
                is_nvidia = True
                description = f"{name} ({vram_gb:.1f} GB VRAM)"
                
                # Check CUDA availability properly via ctranslate2
                try:
                    if HAS_CTRANSLATE2 and ctranslate2.get_cuda_device_count() > 0:
                        device_type = "cuda"
                    else:
                        description += " - (CUDA API Unavailable)"
                except:
                    pass
                    
            except Exception as e:
                logger.debug(f"NVML init failed: {e}")
        
        # 1. Fallback to ctranslate2/torch if NVML didn't run or failed
        if not is_nvidia:
            if HAS_CTRANSLATE2:
                try:
                    count = ctranslate2.get_cuda_device_count()
                    if count > 0:
                        device_type = "cuda"
                        is_nvidia = True # It's CUDA, so it's Nvidia
                        description = "Nvidia GPU (Generic)"
                except Exception as e:
                    logger.warning(f"Error checking CUDA via ctranslate2: {e}")

            # Try to get VRAM via Torch if we haven't got it from NVML
            if is_nvidia and vram_gb == 0.0 and HAS_TORCH:
                try:
                    if torch.cuda.is_available():
                        props = torch.cuda.get_device_properties(0)
                        vram_gb = props.total_memory / (1024**3)
                        description = f"{props.name} ({vram_gb:.1f} GB VRAM)"
                except Exception as e:
                    logger.warning(f"Error getting VRAM via torch: {e}")

        # 2. Check for AMD / Other GPU via WMI (Windows) if not Nvidia
        if device_type == "cpu" and not is_nvidia and platform.system() == "Windows":
             try:
                 import wmi
                 w = wmi.WMI()
                 for video in w.Win32_VideoController():
                     name = video.Name
                     if "AMD" in name or "Radeon" in name:
                         description = f"Detected: {name}"
                         if HardwareManager.is_hip_available():
                             description += " (HIP SDK Detected)"
                         else:
                             description += " (No ROCm/HIP SDK Found)"

                         return DeviceProfile(
                             device_type="cpu", 
                             vram_gb=0, 
                             recommended_model="small", 
                             recommended_compute="int8", 
                             description=description,
                             is_nvidia=False
                         )
                     elif "NVIDIA" in name:
                         # This implies we failed to detect via NVML AND ctranslate2
                         is_nvidia = True
                         description = f"Detected: {name} - (Driver Issue -> Using CPU Mode)"
             except Exception as e:
                 logger.warning(f"WMI check failed: {e}")

        # Recommendations based on data
        if device_type == "cuda":
            return HardwareManager._recommend(device_type, vram_gb, description, is_nvidia)
            
        return DeviceProfile(
            device_type="cpu", 
            vram_gb=vram_gb, 
            recommended_model="small", 
            recommended_compute="int8", 
            description=description,
            is_nvidia=is_nvidia
        )

    @staticmethod
    def _recommend(device_type: str, vram_gb: float, description: str, is_nvidia: bool) -> DeviceProfile:
        rec_model = "base"
        rec_compute = "int8"
        
        if device_type == "cuda":
            if vram_gb > 8.0:
                rec_model = "large-v3"
                rec_compute = "float16"
            elif vram_gb > 4.0:
                rec_model = "medium"
                rec_compute = "float16"
            elif vram_gb > 2.0:
                rec_model = "small"
                rec_compute = "int8"
            else:
                rec_model = "tiny"
                rec_compute = "int8" 
        
        return DeviceProfile(device_type, vram_gb, rec_model, rec_compute, description, is_nvidia)

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
