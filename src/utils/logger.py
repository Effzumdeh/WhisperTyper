import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from .config import config_manager

def setup_logging():
    """Configure logging with RotatingFileHandler and Console output."""
    log_dir = config_manager.paths.data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "whisper_typer.log"
    
    # Format
    log_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # Rotating File Handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024, # 5 MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)
    
    logging.info(f"Logging initialized. Log file: {log_file}")
    
def update_logging_level(debug: bool):
    """
    Updates the logging level and handlers based on debug mode.
    If debug=True: Level=DEBUG, adds debug.log handler.
    If debug=False: Level=INFO, removes debug.log handler.
    """
    root_logger = logging.getLogger()
    
    # Paths
    log_dir = config_manager.paths.data_dir / "logs"
    debug_log_file = log_dir / "debug.log"
    
    if debug:
        root_logger.setLevel(logging.DEBUG)
        
        # Check if we already have a file handler for debug.log
        has_debug_handler = False
        for handler in root_logger.handlers:
            if isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(debug_log_file):
                has_debug_handler = True
                break
                
        if not has_debug_handler:
            # Create Debug Handler
            debug_handler = RotatingFileHandler(
                debug_log_file,
                maxBytes=10 * 1024 * 1024, # 10 MB
                backupCount=3,
                encoding="utf-8"
            )
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s")
            debug_handler.setFormatter(formatter)
            root_logger.addHandler(debug_handler)
            logging.debug("Debug logging enabled.")
            
    else:
        root_logger.setLevel(logging.INFO)
        
        # Remove debug handler
        handlers_to_remove = []
        for handler in root_logger.handlers:
             if isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(debug_log_file):
                 handlers_to_remove.append(handler)
        
        for h in handlers_to_remove:
            h.close()
            root_logger.removeHandler(h)
            
        logging.info("Debug logging disabled.")
