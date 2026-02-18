import sys
import os
import logging
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from src.utils.config import config_manager
from src.utils.logger import update_logging_level

def test_debug_logging():
    print("--- Debug Logging Test ---")
    
    # 1. Enable Debug Mode
    print("Enabling Debug Mode...")
    config_manager.config.debug_mode = True
    update_logging_level(True)
    
    # 2. Log a debug message
    logger = logging.getLogger("TEST")
    test_msg = "This is a verification debug message."
    logger.debug(test_msg)
    
    # 3. Check file
    log_dir = config_manager.paths.data_dir / "logs"
    debug_log = log_dir / "debug.log"
    
    if debug_log.exists():
        print(f"[SUCCESS] debug.log created at {debug_log}")
        content = debug_log.read_text(encoding="utf-8")
        if test_msg in content:
            print("[SUCCESS] Debug message found in log file.")
        else:
            print("[ERROR] Debug message NOT found in log file.")
    else:
         print(f"[ERROR] debug.log NOT found at {debug_log}")

if __name__ == "__main__":
    test_debug_logging()
