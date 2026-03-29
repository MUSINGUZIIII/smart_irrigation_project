import os
import sys
import mimetypes
from urllib.parse import urlparse
from dotenv import load_dotenv
from pathlib import Path
import dj_database_url

# Load environment variables before any other settings
load_dotenv()

# Environment Detection
IS_PRODUCTION = os.getenv('RENDER', 'False').lower() == 'true' or os.getenv('ENVIRONMENT') == 'production'

# Add MIME type for JavaScript files
mimetypes.add_type("application/javascript", ".js", True)


class CorrectMimeTypeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.endswith('.js'):
            response['Content-Type'] = 'application/javascript'
        return response


# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

IS_DEVELOPMENT = not IS_PRODUCTION

# Security Settings
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if IS_DEVELOPMENT:
        SECRET_KEY = 'django-insecure-dev-key-only'  # For development only
    else:
        raise ValueError("SECRET_KEY must be set in production")

# DEBUG = os.getenv('DEBUG', 'False').lower() == 'true' if not IS_PRODUCTION else False
if IS_PRODUCTION:
    DEBUG = False
else:
    debug_env = os.getenv('DEBUG', 'False')
    DEBUG = debug_env.lower() == 'true'

ALLOWED_HOSTS = [
    'smart-irrigation-lefs.onrender.com',
    'localhost',
    '127.0.0.1',
    '192.168.43.176',
]

# Application definition
INSTALLED_APPS = [
    # Third-party apps
    'channels',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_extensions',
    'cloudinary',
    'cloudinary_storage',

    # Local apps
    'accounts.apps.AccountsConfig',
    'irrigation',

    # Django core apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'smart_irrigation.settings.CorrectMimeTypeMiddleware',
    'irrigation.connection_middleware.ConnectionMiddleware',
    'irrigation.db_middleware.DBConnectionMiddleware',
    'irrigation.middleware.ThrottleHeaderMiddleware',
    'irrigation.middleware.block_media_requests_in_production',
]

ROOT_URLCONF = 'smart_irrigation.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Database configuration
if IS_PRODUCTION:
    # Render PostgreSQL configuration
    DATABASES = {
        'default': dj_database_url.config(
            default=os.getenv('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True
        )
    }

else:

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


WHITENOISE_MIMETYPES = {
    '.webmanifest': 'application/manifest+json',
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'irrigation', 'static'),
    os.path.join(BASE_DIR, 'accounts', 'static'),
]


# Tell Django to copy static files into the staticfiles directory
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# settings.py - Cloudinary configuration
if IS_PRODUCTION:
    print("DEBUG: Using Cloudinary for media storage")

    # Use Cloudinary for production
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
        'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
        'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
        'SECURE': True,
        'STATICFILES_MANIFEST_ROOT': os.path.join(BASE_DIR, 'manifest'),
        # Make sure these settings are correct
        'MEDIA_TAG': 'media',
        'INVALIDATE': True,
    }

    # For production, media URLs should point to Cloudinary
    MEDIA_URL = '/media/'  # This will be handled by Cloudinary storage

else:
    print("DEBUG: Using local filesystem for media storage")
    # Local development
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
    MEDIA_URL = '/media/'
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'


# Handle missing files
def get_media_url(file_field):
    """Safe method to get media URL that handles missing files"""
    if not file_field:
        return None

    try:
        if IS_PRODUCTION and hasattr(file_field.storage, 'url'):
            return file_field.storage.url(file_field.name)
        else:
            # Check if file exists locally
            if os.path.exists(file_field.path):
                return file_field.url
            else:
                return None
    except (ValueError, AttributeError, OSError):
        return None


# Authentication
AUTH_USER_MODEL = 'accounts.CustomUser'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'
LOGIN_URL = 'login'

# Email Configuration
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
BREVO_API_KEY = os.getenv('BREVO_API_KEY')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')

# Site information for password reset emails
SITE_ID = 1

SITE_NAME = "Irrigation Intelligent"

IS_WINDOWS = sys.platform.startswith('win')

# Custom irrigation settings - MAKE SURE THIS IS DEFINED
IRRIGATION_SYSTEM = {
    'DEFAULT_SOIL_MOISTURE_THRESHOLD': 50,
    'DEFAULT_WATERING_DURATION': 10,
    'MAX_SENSOR_DATA_AGE': 3600,
    'SENSOR_DATA_INTERVAL': 300,
    'WEBSOCKETS_ENABLED': not IS_WINDOWS  # Disable WebSockets on Windows
}

# Daphne/ASGI settings
ASGI_APPLICATION = 'smart_irrigation.asgi.application'

# Windows-specific settings
if sys.platform.startswith('win'):
    # Disable Channels on Windows to avoid non-blocking I/O issues
    INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'channels']

    # Use different middleware for Windows
    MIDDLEWARE = [mw for mw in MIDDLEWARE if mw not in [
        'irrigation.connection_middleware.ConnectionMiddleware',
        'irrigation.db_middleware.DBConnectionMiddleware'
    ]]

    # Add Windows-compatible middleware
    MIDDLEWARE.insert(0, 'django.middleware.security.SecurityMiddleware')

    # Disable WebSockets on Windows
    IRRIGATION_SYSTEM['WEBSOCKETS_ENABLED'] = False
else:
    IRRIGATION_SYSTEM['WEBSOCKETS_ENABLED'] = True

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'irrigation.authentication.APIKeyAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'irrigation.throttling.DeviceRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '3600/hour',
        'user': '86400/day',
        'device': '12/minute',
    },
}


# Channels configuration
if IS_PRODUCTION:
    # Channels
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [(os.getenv('REDIS_HOST', '127.0.0.1'), int(os.getenv('REDIS_PORT', 6379)))],
            },
        },
    }

else:

    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",  # Use in-memory for development
        }
    }

# Security Settings
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# CORS
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://192.168.43.101:8000",
]
CORS_ORIGIN_ALLOW_ALL = DEBUG  # Only allow all in development

EGOSMS_CONFIG = {
    'USERNAME': os.getenv('EGOSMS_USERNAME'),
    'PASSWORD': os.getenv('EGOSMS_PASSWORD'),
    'SENDER_ID': os.getenv('EGOSMS_SENDER_ID', 'IRRIGATE'),
    'API_URL': os.getenv('EGOSMS_API_URL', 'https://www.egosms.co/api/v1/plain/'),
    'TIMEOUT': 10,  # seconds
    'PRIORITY': 0,  # 0=normal, 1=high
    'TEST_MODE': os.getenv('EGOSMS_TEST_MODE', 'False').lower() == 'true',
}

CRON_SECRET_KEY = os.getenv('CRON_SECRET_KEY', 'dev-secret-key-change-me')

DEFAULT_CHARSET = 'utf-8'

# Celery
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")
url = urlparse(REDIS_URL)

# Celery Configuration for Windows
"""CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'"""
CELERY_WORKER_POOL = 'eventlet'  # Required for Windows
# CELERY_WORKER_CONCURRENCY = 4    # Optimal for Windows
CELERY_TASK_ACKS_LATE = True

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True

CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = 10

CELERY_TASK_ALWAYS_EAGER = False

CELERY_WORKER_CONCURRENCY = 1

CELERY_TIMEZONE = 'Africa/Nairobi'

CELERY_TASK_ROUTES = {
    'irrigation.tasks.send_periodic_sms_alerts': {
        'queue': 'sms_alerts',
        'rate_limit': '10/m'  # Prevent SMS flooding
    }
}

CELERY_BEAT_SCHEDULE = {
    'send-sms-alerts': {
        'task': 'irrigation.tasks.send_periodic_sms_alerts',
        'schedule': 5.0,  # Check every 5 seconds
        'options': {
            'expires': 4,  # Prevent duplicate runs
            'queue': 'sms_alerts'
        }
    }
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG' if DEBUG else 'INFO',
    },
}

# MQTT Settings
MQTT_HOST = os.getenv('MQTT_HOST', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_USER', 'django_server')
MQTT_PASS = os.getenv('MQTT_PASS', 'serverpass')


# Ensure directories exist - only in development
if IS_DEVELOPMENT:
    try:
        os.makedirs(os.path.join(MEDIA_ROOT, 'profile_pics'), exist_ok=True)
        os.makedirs(STATIC_ROOT, exist_ok=True)
        os.makedirs(os.path.join(BASE_DIR, 'irrigation', 'static', 'irrigation', 'images'), exist_ok=True)
        os.makedirs(os.path.join(BASE_DIR, 'accounts', 'static'), exist_ok=True)
    except OSError as e:
        print(f"Warning: Could not create directories: {e}")
