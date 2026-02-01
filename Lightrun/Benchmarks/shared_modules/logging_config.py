import logging
import sys

class InfoFilter(logging.Filter):
    """Filter to allow only records with level < WARNING (i.e., INFO and DEBUG)."""
    def filter(self, record):
        return record.levelno < logging.WARNING

def configure_logger(logger: logging.Logger) -> None:
    """
    Configures the logger to log:
    - stdout: INFO level (filtered to exclude WARNING and ERROR)
    - stderr: WARNING and ERROR levels
    - file: INFO level and above, filename is {logger.name}.log
    """
    # clear existing handlers
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
    file_handler = logging.FileHandler(f"{logger.name}.log")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
