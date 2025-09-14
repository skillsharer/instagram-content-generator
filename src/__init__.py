"""Instagram Content Generator - Automated content analysis and posting."""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"
__description__ = "Automated Instagram content generator with AI-powered analysis and caption generation"

from .modules.config_manager import config
from .modules.scheduler import InstagramScheduler
from .modules.monitoring import system_monitor

__all__ = [
    "config",
    "InstagramScheduler", 
    "system_monitor",
]