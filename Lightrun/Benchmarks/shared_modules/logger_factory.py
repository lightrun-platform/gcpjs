import logging
import sys
from pathlib import Path
from typing import Any


class InfoFilter(logging.Filter):
    """Filter to allow only records with level < WARNING (i.e., INFO and DEBUG)."""
    def filter(self, record):
        return record.levelno < logging.WARNING

class LoggerFactory:
    """Factory for creating configured loggers."""

    def __init__(self, log_dir: Path):
        """
        Initialize the factory.

        Args:
            log_dir: Directory where log files should be saved.
        """
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup global log file handler
        self.global_log_file = self.log_dir / "benchmark_run.log"
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.global_file_handler = logging.FileHandler(self.global_log_file, mode='a')
        self.global_file_handler.setLevel(logging.INFO)
        self.global_file_handler.setFormatter(formatter)


    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a configured logger.
        
        Configures the logger to log:
        - stdout: INFO level (filtered to exclude WARNING and ERROR)
        - stderr: WARNING and ERROR levels
        - file: INFO level and above, filename is {log_dir}/{name}.log
        - global file: INFO level and above, filename is {log_dir}/benchmark_run.log
        """

        logger = logging.getLogger(name)
        
        # clear existing handlers to avoid duplicates if get_logger is called multiple times
        if logger.handlers:
            logger.handlers.clear()
            
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # stdout handler for INFO (and DEBUG if enabled)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.INFO)
        stdout_handler.setFormatter(formatter)
        stdout_handler.addFilter(InfoFilter())
        logger.addHandler(stdout_handler)
        
        # stderr handler for WARNING/ERROR
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.WARNING)
        stderr_handler.setFormatter(formatter)
        logger.addHandler(stderr_handler)
        
        # file handler
        log_file = self.log_dir / f"{name}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # global file handler
        logger.addHandler(self.global_file_handler)
        
        return logger
