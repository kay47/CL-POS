import os
from urllib.parse import quote_plus
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production-2024'
    
    # PostgreSQL Configuration - External Database
    # Format: postgresql://username:password@host:port/database_name
    
    # Option 1: Use full DATABASE_URL (recommended for external databases)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f"postgresql://{os.environ.get('POSTGRES_USER', 'postgres')}:" \
        f"{quote_plus(os.environ.get('POSTGRES_PASSWORD', 'password'))}@" \
        f"{os.environ.get('POSTGRES_HOST', 'localhost')}:" \
        f"{os.environ.get('POSTGRES_PORT', '5432')}/" \
        f"{os.environ.get('POSTGRES_DB', 'mylord_pos_db')}"
    
    # SQLAlchemy settings
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False  # Set to True for SQL query logging
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,  # Enable connection health checks
        'connect_args': {
            'connect_timeout': 10,
            'options': '-c timezone=utc'
        }
    }
    
    # Upload folders
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'static', 'uploads')
    PRODUCT_IMAGES_FOLDER = os.path.join(UPLOAD_FOLDER, 'product_images')
    EXPENSE_DOCUMENTS_FOLDER = os.path.join(UPLOAD_FOLDER, 'expense_documents')
    
    # Ensure upload folders exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(PRODUCT_IMAGES_FOLDER, exist_ok=True)
    os.makedirs(EXPENSE_DOCUMENTS_FOLDER, exist_ok=True)
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'doc', 'docx'}
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_ECHO = True  # Log SQL queries in development
    
    # Development-specific settings
    TEMPLATES_AUTO_RELOAD = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_ECHO = False
    
    # Production must have these set via environment variables
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable must be set in production")
    
    # SSL mode for production databases
    if os.environ.get('DATABASE_URL'):
        # Handle Heroku/Railway DATABASE_URL format
        uri = os.environ.get('DATABASE_URL')
        if uri and uri.startswith('postgres://'):
            uri = uri.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = uri
        
        # Add SSL requirement for production
        if 'sslmode' not in SQLALCHEMY_DATABASE_URI:
            SQLALCHEMY_DATABASE_URI += '?sslmode=require'
    
    # Secure session cookies
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    
    # Production pool settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'max_overflow': 10,
        'pool_recycle': 1800,
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 10,
            'options': '-c timezone=utc'
        }
    }


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    # Use in-memory SQLite for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_database_url():
    """Helper function to get database URL with proper formatting"""
    # Check for full DATABASE_URL first (common in cloud platforms)
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # Fix postgres:// to postgresql:// (Heroku/Railway compatibility)
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return database_url
    
    # Build from individual components
    user = os.environ.get('POSTGRES_USER', 'postgres')
    password = os.environ.get('POSTGRES_PASSWORD', '')
    host = os.environ.get('POSTGRES_HOST', 'localhost')
    port = os.environ.get('POSTGRES_PORT', '5432')
    database = os.environ.get('POSTGRES_DB', 'mylord_pos_db')
    
    # URL encode password to handle special characters
    encoded_password = quote_plus(password)
    
    return f"postgresql://{user}:{encoded_password}@{host}:{port}/{database}"