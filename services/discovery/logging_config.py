import logging
import sys

def setup_logging():
    """Configure logging for the discovery service."""
    # Create a formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    
    file_handler = logging.FileHandler('discovery.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add our handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Set specific loggers to DEBUG
    loggers = [
        'services.discovery',
        'services.discovery.tasks',
        'services.discovery.service',
        'services.discovery.strategies',
        'services.discovery.strategies.weather',
        'services.discovery.strategies.github',
        'services.discovery.strategies.openapi_strategy',
        'services.discovery.strategies.google_discovery',
        'services.discovery.strategies.generic_llm'
    ]
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG) 