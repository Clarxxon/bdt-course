# superset_config.py
import os

# Secret key for session signing
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "your-secret-key-here")

# Database configuration
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://{os.environ.get('SUPERSET_DATABASE_USER')}:"
    f"{os.environ.get('SUPERSET_DATABASE_PASSWORD')}@"
    f"{os.environ.get('SUPERSET_DATABASE_HOST')}:"
    f"{os.environ.get('SUPERSET_DATABASE_PORT')}/"
    f"{os.environ.get('SUPERSET_DATABASE_NAME')}"
)

# Redis configuration for caching and async queries
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)

CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'superset_',
    'CACHE_REDIS_HOST': REDIS_HOST,
    'CACHE_REDIS_PORT': REDIS_PORT,
    'CACHE_REDIS_DB': 0,
}

DATA_CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 86400,
    'CACHE_KEY_PREFIX': 'data_',
    'CACHE_REDIS_HOST': REDIS_HOST,
    'CACHE_REDIS_PORT': REDIS_PORT,
    'CACHE_REDIS_DB': 1,
}

FILTER_STATE_CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 86400,
    'CACHE_KEY_PREFIX': 'filter_',
    'CACHE_REDIS_HOST': REDIS_HOST,
    'CACHE_REDIS_PORT': REDIS_PORT,
    'CACHE_REDIS_DB': 2,
}

EXPLORE_FORM_DATA_CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 86400,
    'CACHE_KEY_PREFIX': 'explore_',
    'CACHE_REDIS_HOST': REDIS_HOST,
    'CACHE_REDIS_PORT': REDIS_PORT,
    'CACHE_REDIS_DB': 3,
}

# Celery configuration
class CeleryConfig:
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    imports = ("superset.sql_lab",)
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    worker_prefetch_multiplier = 1
    task_acks_late = False
    task_annotations = {
        'sql_lab.get_sql_results': {
            'rate_limit': '100/s'
        }
    }

CELERY_CONFIG = CeleryConfig

# Feature flags
FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
    "ALERT_REPORTS": True,
}

# Security settings
WTF_CSRF_ENABLED = True
WTF_CSRF_TIME_LIMIT = 3600

# File upload settings
UPLOAD_FOLDER = "/app/superset_home/uploads"
MAX_UPLOAD_SIZE = 16 * 1024 * 1024  # 16MB

# Enable proxy fix if behind a reverse proxy
ENABLE_PROXY_FIX = True