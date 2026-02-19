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
    Updates the logging level based on debug mode.
    If debug=True: Level=DEBUG.
    If debug=False: Level=INFO.
    Logs always go to whisper_typer.log (single file).
    """
    root_logger = logging.getLogger()
    
    if debug:
        root_logger.setLevel(logging.DEBUG)
        logging.debug("Debug logging enabled (Level: DEBUG).")
    else:
        root_logger.setLevel(logging.INFO)
        logging.info("Debug logging disabled (Level: INFO).")
