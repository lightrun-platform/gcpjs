import logging
import sys

class InfoFilter(logging.Filter):
    """Filter to allow only records with level < WARNING (i.e., INFO and DEBUG)."""
    def filter(self, record):
        return record.levelno < logging.WARNING