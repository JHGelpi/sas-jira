import os
import yaml
import logging
import logging.config

def setup_logging():
    """
    Loads logging configuration from the log_config.yaml file
    and sets it up for the application.
    """
    # Define the path to the config file relative to this script
    config_path = os.path.join(os.path.dirname(__file__), 'log_config.yaml')
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'rt') as f:
                config = yaml.safe_load(f.read())
            
            # Ensure the logs directory exists
            log_dir = os.path.join(os.path.dirname(__file__), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            # Apply the configuration
            logging.config.dictConfig(config)
            logging.info("Logging configured successfully from log_config.yaml.")
        except Exception as e:
            # Fallback to basic config if YAML loading fails
            logging.basicConfig(level=logging.INFO)
            logging.error(f"Failed to load logging configuration from YAML: {e}")
            logging.warning("Fell back to basic logging configuration.")
    else:
        # Fallback if the config file is missing
        logging.basicConfig(level=logging.INFO)
        logging.warning("log_config.yaml not found. Using basic logging configuration.")

