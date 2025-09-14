"""Configuration management for Instagram Content Generator."""

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Instagram API Configuration
    instagram_username: str = Field(default="", env="INSTAGRAM_USERNAME")
    instagram_password: str = Field(default="", env="INSTAGRAM_PASSWORD")
    
    # OpenAI API Configuration
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    
    # File system paths
    shared_folder_path: Path = Field(default=Path("/shared"), env="SHARED_FOLDER_PATH")
    processed_folder_path: Path = Field(default=Path("/processed"), env="PROCESSED_FOLDER_PATH")
    
    # Scheduling configuration
    scan_interval_minutes: int = Field(default=30, env="SCAN_INTERVAL_MINUTES")
    upload_delay_minutes: int = Field(default=60, env="UPLOAD_DELAY_MINUTES")
    
    # Content analysis settings
    max_caption_length: int = Field(default=2200, env="MAX_CAPTION_LENGTH")
    use_hashtags: bool = Field(default=True, env="USE_HASHTAGS")
    max_hashtags: int = Field(default=30, env="MAX_HASHTAGS")
    
    # Instagram upload settings
    upload_quality: str = Field(default="high", env="UPLOAD_QUALITY")
    video_max_size_mb: int = Field(default=100, env="VIDEO_MAX_SIZE_MB")
    image_max_size_mb: int = Field(default=8, env="IMAGE_MAX_SIZE_MB")
    
    # Logging configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file_path: Path = Field(
        default=Path("/var/log/instagram-content-generator.log"), 
        env="LOG_FILE_PATH"
    )
    
    # Health check settings
    health_check_port: int = Field(default=8080, env="HEALTH_CHECK_PORT")
    health_check_enabled: bool = Field(default=True, env="HEALTH_CHECK_ENABLED")
    
    # AI Model settings
    content_analysis_model: str = Field(
        default="openai/clip-vit-base-patch32", 
        env="CONTENT_ANALYSIS_MODEL"
    )
    caption_generation_model: str = Field(default="gpt-4", env="CAPTION_GENERATION_MODEL")
    caption_temperature: float = Field(default=0.7, env="CAPTION_TEMPERATURE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class ConfigManager:
    """Manages application configuration and environment setup."""
    
    def __init__(self, env_file: Optional[str] = None):
        """Initialize configuration manager.
        
        Args:
            env_file: Path to environment file. If None, uses default .env
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        self.settings = Settings()
        # Don't create directories on init - do it lazily when needed
    
    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        directories = [
            self.settings.shared_folder_path,
            self.settings.processed_folder_path,
            self.settings.log_file_path.parent,
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_user_paths(self, username: str) -> dict[str, Path]:
        """Get file paths for a specific Instagram user.
        
        Args:
            username: Instagram username
            
        Returns:
            Dictionary containing user-specific paths
        """
        user_base = self.settings.shared_folder_path / username
        processed_base = self.settings.processed_folder_path / username
        
        paths = {
            "videos": user_base / "videos",
            "images": user_base / "images", 
            "processed_videos": processed_base / "videos",
            "processed_images": processed_base / "images",
            "queue": processed_base / "queue",
            "failed": processed_base / "failed",
        }
        
        # Ensure user directories exist
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
            
        return paths
    
    def validate_instagram_credentials(self) -> bool:
        """Validate that Instagram credentials are provided.
        
        Returns:
            True if credentials are valid, False otherwise
        """
        return bool(
            self.settings.instagram_username and 
            self.settings.instagram_password
        )
    
    def validate_openai_credentials(self) -> bool:
        """Validate that OpenAI credentials are provided.
        
        Returns:
            True if credentials are valid, False otherwise  
        """
        return bool(self.settings.openai_api_key)


# Global configuration instance
config = ConfigManager()