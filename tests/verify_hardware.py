import sys
import os
import logging

# Add project root to path
sys.path.append(os.getcwd())

from src.utils.hardware import HardwareManager
from src.utils.config import config_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFY")

def test_hardware_detection():
    print("--- Hardware Detection Test ---")
    try:
        profile = HardwareManager.get_profile()
        print(f"Device Type: {profile.device_type}")
        print(f"VRAM: {profile.vram_gb:.2f} GB")
        print(f"Description: {profile.description}")
        print(f"Is Nvidia: {profile.is_nvidia}")
        print(f"Rec. Model: {profile.recommended_model}")
        print(f"Rec. Compute: {profile.recommended_compute}")
        
        if profile.is_nvidia:
            print("\n[SUCCESS] Nvidia GPU detected successfully.")
        else:
            print("\n[INFO] No Nvidia GPU detected (or pynvml failed). This is expected if you don't have one.")
            
    except Exception as e:
        print(f"\n[ERROR] Hardware detection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_hardware_detection()
