"""
Configuration management for VPS-based streaming license system.
Loads configuration from environment variables with sensible defaults.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables with this precedence:
# 1) OS environment
# 2) .env.local (developer/machine specific, should stay untracked)
# 3) .env (safe defaults/templates)
env_dir = os.path.dirname(__file__)
for env_name in ('.env.local', '.env'):
    env_path = os.path.join(env_dir, env_name)
    if os.path.exists(env_path):
        load_dotenv(env_path, override=False)


class Config:
    """Application configuration loaded from environment variables."""
    
    # Flask configuration
    SECRET_KEY: str = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG: bool = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Database configuration
    DATABASE_URL: str = os.environ.get(
        'DATABASE_URL',
        'postgresql://cipher_user:cipher_pass@localhost:5432/cipher_license'
    )
    DB_POOL_SIZE: int = int(os.environ.get('DB_POOL_SIZE', '10'))
    DB_POOL_MAX_OVERFLOW: int = int(os.environ.get('DB_POOL_MAX_OVERFLOW', '20'))
    DB_POOL_TIMEOUT: int = int(os.environ.get('DB_POOL_TIMEOUT', '30'))
    
    # JWT configuration
    JWT_SECRET_KEY: str = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-change-in-production')
    JWT_EXPIRATION_MINUTES: int = int(os.environ.get('JWT_EXPIRATION_MINUTES', '5'))
    
    # AES encryption configuration
    AES_ENCRYPTION_KEY: Optional[str] = os.environ.get('AES_ENCRYPTION_KEY')
    
    # Binary storage
    BINARY_STORAGE_PATH: str = os.environ.get(
        'BINARY_STORAGE_PATH',
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'binaries')
    )
    
    # Rate limiting
    RATE_LIMIT_AUTH: str = os.environ.get('RATE_LIMIT_AUTH', '10 per minute')
    RATE_LIMIT_API: str = os.environ.get('RATE_LIMIT_API', '60 per minute')
    
    # Session management
    SESSION_CLEANUP_INTERVAL_MINUTES: int = int(os.environ.get('SESSION_CLEANUP_INTERVAL_MINUTES', '5'))
    SESSION_HEARTBEAT_TIMEOUT_SECONDS: int = int(os.environ.get('SESSION_HEARTBEAT_TIMEOUT_SECONDS', '90'))
    
    # Admin authentication
    ADMIN_TOKEN: str = os.environ.get('ADMIN_TOKEN', 'admin-token-change-in-production')
    ADMIN_REQUIRE_TOKEN: bool = os.environ.get('ADMIN_REQUIRE_TOKEN', 'True').lower() == 'true'
    ADMIN_LOCALHOST_ONLY: bool = os.environ.get('ADMIN_LOCALHOST_ONLY', 'False').lower() == 'true'
    
    # Logging
    LOG_LEVEL: str = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE: str = os.environ.get('LOG_FILE', 'api_server.log')
    LOG_MAX_BYTES: int = int(os.environ.get('LOG_MAX_BYTES', str(10 * 1024 * 1024)))  # 10MB
    LOG_BACKUP_COUNT: int = int(os.environ.get('LOG_BACKUP_COUNT', '5'))
    
    @classmethod
    def validate(cls) -> None:
        """Validate critical configuration values."""
        if cls.SECRET_KEY == 'dev-secret-key-change-in-production':
            print("WARNING: Using default SECRET_KEY. Set SECRET_KEY environment variable in production.")
        
        if cls.JWT_SECRET_KEY == 'jwt-secret-change-in-production':
            print("WARNING: Using default JWT_SECRET_KEY. Set JWT_SECRET_KEY environment variable in production.")
        
        if not cls.AES_ENCRYPTION_KEY:
            print("WARNING: AES_ENCRYPTION_KEY not set. Binary encryption/decryption will not work.")
        
        if cls.ADMIN_TOKEN == 'admin-token-change-in-production':
            print("WARNING: Using default ADMIN_TOKEN. Set ADMIN_TOKEN environment variable in production.")

        if not cls.ADMIN_REQUIRE_TOKEN:
            print("WARNING: ADMIN_REQUIRE_TOKEN is disabled. Admin routes will accept requests without a token.")
