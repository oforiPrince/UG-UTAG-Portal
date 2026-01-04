"""Django settings for utag_ug_archiver project with env overrides."""

import os
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-placeholder')


def _env_bool(name: str, default: bool = False) -> bool:
    """Return boolean env value with sensible defaults."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = _env_bool('DJANGO_DEBUG', default=True)


def _env_list(name: str, default=None):
    raw = os.environ.get(name)
    if not raw:
        return default or []
    return [item.strip() for item in raw.split(',') if item.strip()]


# Load allowed hosts from environment. Support either DJANGO_ALLOWED_HOSTS or ALLOWED_HOSTS
# Value should be a comma separated list, e.g. DJANGO_ALLOWED_HOSTS=197.255.126.246,example.com
allowed_from_django = _env_list('DJANGO_ALLOWED_HOSTS')
allowed_from_generic = _env_list('ALLOWED_HOSTS')
if allowed_from_django:
    ALLOWED_HOSTS = allowed_from_django
elif allowed_from_generic:
    ALLOWED_HOSTS = allowed_from_generic
else:
    # sane default for development
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'adverts',
    'accounts',
    'dashboard',
    'chat',
    'gallery',
    'website',
    
    #External libraries
    'import_export',
    'tinymce',
    'django_celery_beat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

ROOT_URLCONF = 'utag_ug_archiver.urls'

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

WSGI_APPLICATION = 'utag_ug_archiver.wsgi.application'
ASGI_APPLICATION = 'utag_ug_archiver.asgi.application'

redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/1')

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [redis_url],
        },
    },
}


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

def _database_from_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in {'postgres', 'postgresql'}:
        raise ValueError('Unsupported database scheme in DATABASE_URL.')

    db_config = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': (parsed.path or '/postgres').lstrip('/'),
        'USER': parsed.username or '',
        'PASSWORD': parsed.password or '',
        'HOST': parsed.hostname or '',
        'PORT': str(parsed.port) if parsed.port else '',
    }

    options = dict(parse_qsl(parsed.query))
    if options:
        db_config['OPTIONS'] = options

    return db_config


def _database_from_env():
    engine = os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3')
    if engine == 'django.db.backends.sqlite3':
        return {
            'ENGINE': engine,
            'NAME': os.environ.get('SQLITE_NAME', BASE_DIR / 'db.sqlite3'),
        }

    db_config = {
        'ENGINE': engine,
        'NAME': os.environ.get('DB_NAME') or os.environ.get('POSTGRES_DB', ''),
        'USER': os.environ.get('DB_USER') or os.environ.get('POSTGRES_USER', ''),
        'PASSWORD': os.environ.get('DB_PASSWORD') or os.environ.get('POSTGRES_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }

    ssl_mode = os.environ.get('DB_SSL_MODE')
    if ssl_mode:
        db_config['OPTIONS'] = {'sslmode': ssl_mode}

    return db_config


database_url = os.environ.get('DATABASE_URL')

if database_url:
    if DEBUG:
        # Stick with SQLite (or DB_* overrides) during development even if DATABASE_URL is present for easier onboarding
        DATABASES = {'default': _database_from_env()}
    elif database_url:
        DATABASES = {'default': _database_from_url(database_url)}
    else:
        DATABASES = {'default': _database_from_env()}
else:
    DATABASES = {'default': _database_from_env()}

conn_max_age = os.environ.get('DB_CONN_MAX_AGE')
if conn_max_age:
    DATABASES['default']['CONN_MAX_AGE'] = int(conn_max_age)
else:
    # Default connection pooling for production
    if not DEBUG:
        DATABASES['default']['CONN_MAX_AGE'] = 600  # 10 minutes


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = os.environ.get('STATIC_URL', '/static/')
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
# static root
STATIC_ROOT = os.environ.get('STATIC_ROOT', os.path.join(BASE_DIR, 'staticfiles'))

# Use WhiteNoise to serve static files directly from Gunicorn in simple deployments
STATICFILES_STORAGE = os.environ.get(
    'DJANGO_STATICFILES_STORAGE', 'whitenoise.storage.CompressedStaticFilesStorage'
)


MEDIA_URL = os.environ.get('MEDIA_URL', '/media/')
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', os.path.join(BASE_DIR, 'media'))

X_FRAME_OPTIONS = 'ALLOWALL'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email settings
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_USE_TLS = _env_bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = _env_bool('EMAIL_USE_SSL', default=False)
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 
TINYMCE_DEFAULT_CONFIG = {
    'height': 360,
    'width': 800,
    'cleanup_on_startup': True,
    'custom_undo_redo_levels': 20,
    'selector': 'textarea',
    'theme': 'modern',
    'plugins': '''
        textcolor save link image media preview codesample contextmenu
        table code lists fullscreen  insertdatetime  nonbreaking
        contextmenu directionality searchreplace wordcount visualblocks
        visualchars code fullscreen autolink lists  charmap print  hr
        anchor pagebreak
    ''',
    'toolbar1': '''
        fullscreen preview bold italic underline | fontselect,
        fontsizeselect  | forecolor backcolor | alignleft alignright |
        aligncenter alignjustify | indent outdent | bullist numlist table |
        | link image media | codesample
    ''',
    'toolbar2': '''
        visualblocks visualchars |
        charmap hr pagebreak nonbreaking anchor |  code |
        save insertdatetime  media  | print preview
    ''',
    'contextmenu': 'formats | link image',
    'menubar': True,
    'statusbar': True,
}


# Celery Configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Cache Configuration
try:
    import django_redis
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.environ.get('REDIS_CACHE_URL', 'redis://localhost:6379/2'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
                'IGNORE_EXCEPTIONS': True,  # Don't fail if Redis is unavailable
            },
            'KEY_PREFIX': 'utag_ug',
            'TIMEOUT': 300,  # 5 minutes default timeout
        }
    }
except ImportError:
    # Fallback to local memory cache if django-redis is not installed
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }

# Session caching for better performance
if not DEBUG:
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'

# Template caching for production
if not DEBUG:
    TEMPLATES[0]['OPTIONS']['loaders'] = [
        ('django.template.loaders.cached.Loader', [
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        ]),
    ]

# WhiteNoise configuration for production
if not DEBUG:
    WHITENOISE_USE_FINDERS = False
    WHITENOISE_AUTOREFRESH = False
    WHITENOISE_MANIFEST_STRICT = True
    # Add max-age for static files
    WHITENOISE_MAX_AGE = 31536000  # 1 year

# Security settings for production
if not DEBUG:
    SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

csrf_trusted_origins = _env_list('CSRF_TRUSTED_ORIGINS')
if csrf_trusted_origins:
    CSRF_TRUSTED_ORIGINS = csrf_trusted_origins

# Performance optimizations
if not DEBUG:
    # Disable admin documentation in production
    ADMINS = []
    
    # Optimize logging
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
            'level': 'WARNING',
        },
        'loggers': {
            'django': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.db.backends': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False,
            },
        },
    }