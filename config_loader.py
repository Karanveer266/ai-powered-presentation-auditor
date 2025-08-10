"""
Configuration loader for the PowerPoint inconsistency detector.
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file with validation."""
    
    config_file = Path(config_path)
    
    if not config_file.exists():
        logger.warning(f"Config file {config_path} not found. Using default configuration.")
        return get_default_config()
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Validate required sections
        required_sections = ['gemini', 'system']
        for section in required_sections:
            if section not in config:
                logger.warning(f"Missing required config section: {section}")
                config[section] = {}
        
        # Apply defaults for missing values
        config = merge_with_defaults(config)
        
        logger.debug("Configuration loaded successfully")
        return config
    
    except Exception as e:
        logger.error(f"Failed to load configuration from {config_path}: {e}")
        logger.info("Using default configuration")
        return get_default_config()


def get_default_config() -> Dict[str, Any]:
    """Get default configuration for free tier usage."""
    return {
        'gemini': {
            'api_key_env': 'GEMINI_API_KEY',
            'model': 'gemini-2.0-flash-exp',
            'request_delay': 8,
            'max_retries': 2,
            'quota_wait_time': 60
        },
        'system': {
            'version': '2.1.0-free-tier',
            'optimization': 'minimal_api_calls',
            'max_slides_recommended': 20
        },
        'detection': {
            'percentage_tolerance': 2,
            'confidence_threshold': 0.7
        },
        'logging': {
            'level': 'INFO',
            'api_call_tracking': True
        }
    }


def merge_with_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge loaded config with default values for missing keys."""
    defaults = get_default_config()
    
    for section, section_defaults in defaults.items():
        if section not in config:
            config[section] = section_defaults
        else:
            for key, default_value in section_defaults.items():
                if key not in config[section]:
                    config[section][key] = default_value
    
    return config
