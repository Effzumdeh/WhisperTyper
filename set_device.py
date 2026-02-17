import json
import sys
from pathlib import Path
from src.utils.config import config_manager

def set_device(device_id: int):
    print(f"Setting input_device_id to: {device_id}")
    
    # Update object
    config_manager.config.input_device_id = device_id
    config_manager.save_config()
    
    # Verify
    config_path = config_manager.paths.get_config_path()
    print(f"Config saved to: {config_path}")
    print("New Config Content:")
    with open(config_path, 'r', encoding='utf-8') as f:
        print(f.read())

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python set_device.py <DEVICE_ID>")
        sys.exit(1)
        
    try:
        dev_id = int(sys.argv[1])
        set_device(dev_id)
    except ValueError:
        print("Error: Device ID must be an integer.")
