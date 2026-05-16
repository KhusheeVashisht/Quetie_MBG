"""
Configuration management for Quetie_mbg
Environment variables are loaded from .env file or system environment
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    """Application settings loaded from environment variables"""
    
    # Twitch Bot Configuration
    TWITCH_BOT_USERNAME: str = "miss_brain_glitch_bot"
    TWITCH_TARGET_CHANNEL: str = "miss_brain_glitch"
    TWITCH_CLIENT_SECRET: str = os.getenv("TWITCH_CLIENT_SECRET", "")
    TWITCH_ACCESS_TOKEN: str = os.getenv("TWITCH_ACCESS_TOKEN", "")
    TWITCH_REFRESH_TOKEN: str = os.getenv("TWITCH_REFRESH_TOKEN", "")
    TWITCH_OAUTH_TOKEN: str = os.getenv("TWITCH_OAUTH_TOKEN", "")
    TWITCH_CLIENT_ID: str = os.getenv("TWITCH_CLIENT_ID", "")

    def __post_init__(self):
        # Twitch IRC requires oauth:<token> format in PASS command.
        if not self.TWITCH_OAUTH_TOKEN and self.TWITCH_ACCESS_TOKEN:
            self.TWITCH_OAUTH_TOKEN = f"oauth:{self.TWITCH_ACCESS_TOKEN}"
    
    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./quetie.db")
    
    # Web Configuration
    WEB_HOST: str = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT: int = int(os.getenv("WEB_PORT", "8000"))
    WEB_WORKERS: int = int(os.getenv("WEB_WORKERS", "4"))
    
    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Admin Configuration
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD_HASH: str = os.getenv("ADMIN_PASSWORD_HASH", "")
    
    # Application Settings
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO" if not DEBUG else "DEBUG")
    
    # Queue Configuration
    MAX_QUEUE_SIZE: int = 100
    LINK_VALIDATION_TIMEOUT: int = 5  # seconds
    
    # Feature Flags
    ENABLE_HEALTH_CHECK: bool = True
    HEALTH_CHECK_PATH: str = "/health"
    
    def validate(self) -> bool:
        """Validate critical settings"""
        if not self.TWITCH_OAUTH_TOKEN and self.ENVIRONMENT == "production":
            raise ValueError("TWITCH_OAUTH_TOKEN is required in production")
        if not self.JWT_SECRET or self.JWT_SECRET == "dev-secret-key-change-in-production":
            if self.ENVIRONMENT == "production":
                raise ValueError("JWT_SECRET must be set and secure in production")
        return True
    
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.ENVIRONMENT == "production"
    
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.ENVIRONMENT == "development"


# Global settings instance
settings = Settings()

# Validate settings on import
try:
    settings.validate()
except ValueError as e:
    import warnings
    warnings.warn(f"Settings validation warning: {e}")
