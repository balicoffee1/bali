import os
from datetime import timedelta
from pathlib import Path

import environ

# CSRF_TRUSTED_ORIGINS = ['http://localhost', 'https://*.127.0.0.1',
#                         "http://79.174.81.151:8000"]

os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      "island_bali.settings")

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env()

SECRET_KEY = env.str("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# Application definition

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "phonenumber_field",
    "drf_yasg",
    "django_celery_beat",
    "django_extensions",
    'colorfield',
    "django_filters"
]

YOUR_APPS = [
    "users.apps.UsersConfig",
    "orders.apps.OrdersConfig",
    "coffee_shop.apps.CoffeeShopConfig",
    "menu_coffee_product.apps.MenuCoffeeProductConfig",
    "cart.apps.CartConfig",
    "franchise.apps.FranchiseConfig",
    "music_api.apps.MusicApiConfig",
    "bonus_system.apps.BonusSystemConfig",
    "staff.apps.StaffConfig",
    "reviews.apps.ReviewsConfig",
    "subtotal_api.apps.SubtotalApiConfig",
    "ref_system.apps.RefSystemConfig",
    "acquiring.apps.AcquiringConfig",
    "quickresto.apps.QuickrestoConfig",
    "seo.apps.SeoConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + YOUR_APPS
APPEND_SLASH = True
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "island_bali.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "island_bali.wsgi.application"
# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.getenv('DB_NAME'),
#         'USER': os.getenv('POSTGRES_USER'),
#         'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'island_bali',
#         'USER': 'postgres',
#         'PASSWORD': '12345',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }

# DATABASES = {
#     'default': env.db()
# }

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD")

SMS_LOGIN = "fivcoffe0711"
SMS_PASSWORD = "578613"
TELEGRAM_BOT_TOKEN = '7587318359:AAF4StdmIOlHw2eHRTPxLbYRW1eY2gcCtIc'


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

AUTH_USER_MODEL = "users.CustomUser"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.coreapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        days=env.int("ACCESS_TOKEN_LIFETIME", 7)),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("REFRESH_TOKEN_LIFETIME", 30)),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(
        days=env.int("ACCESS_TOKEN_LIFETIME", 7)),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(
        days=env.int("REFRESH_TOKEN_LIFETIME", 30)
    ),
}

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

GROUPS = {"owner": {}, "admin": {}, "employee": {}, "user": {}}

LANGUAGE_CODE = "ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "/static/"

STATIC_ROOT = os.path.join(BASE_DIR, 'static')

MEDIA_URL = ''
MEDIA_ROOT = os.path.join(BASE_DIR, '')

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"



CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
# в течение какого срока храним результаты, после чего они удаляются
CELERY_TASK_RESULT_EXPIRES = 7 * 86400  # 7 days
# это нужно для мониторинга наших воркеров
CELERY_SEND_EVENTS = True
# место хранения периодических задач (данные для планировщика)
CELERYBEAT_SCHEDULER = "djcelery.schedulers.DatabaseScheduler"

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

URL_SUB_TOTAL = env.str("URL_SUB_TOTAL")

RUSSIAN_STANDARD_BASE_URL = env.str("RUSSIAN_STANDARD_BASE_URL")

CART_SESSION_ID = 'cart'

# CSRF_COOKIE_SECURE = True
# ADMINS = [("Admin", "makhotin.07@gmail.com")], [
#     ("Nikita", "nikitka2121@gmail.com")]
SERVER_EMAIL = env.str("EMAIL_HOST_USER")





LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'debug.log'),
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'island_bali': {  # Логирование вашего приложения (замените на название вашего приложения)
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}



SSL_CERT_PATH = os.path.join(BASE_DIR, 'cert/9298136607.pem') 
SSL_KEY_PATH = os.path.join(BASE_DIR, 'cert/private.key')
CA_CERT_PATH = os.path.join(BASE_DIR, 'cert/chain-ecomm-ca-root-ca.crt')


ONESIGNAL_APP_ID = "b522f8d7-ccd4-4fda-9e85-e73baa42aaf3"
ONESIGNAL_API_KEY = "os_v2_app_wurprv6m2rh5vhuf4452uqvk6prcnvlpoudeft4763v3672gyearsk7r3uvtixonozwkyatvpup7f774na2ijksizxfrmaqparqpz5q"