import os
from datetime import timedelta
from pathlib import Path

import environ

CSRF_TRUSTED_ORIGINS = [
    'http://localhost',
    'http://127.0.0.1',
    'https://*.ngrok-free.app',
    'https://*.ngrok.io',
    'http://79.174.81.151',
    'https://79.174.81.151',
]

os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      "island_bali.settings")

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env()

SECRET_KEY = env.str("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

TELEGRAM_BOT_TOKEN = env.str("TELEGRAM_BOT_TOKEN")
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
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "phonenumber_field",
    "drf_yasg",
    "django_celery_beat",
    "django_extensions",
    'colorfield',
    "django_filters",
    "fcm_django",
    "channels",
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
    "admin_api.apps.AdminApiConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + YOUR_APPS
APPEND_SLASH = True

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000"],
)
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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

# M2: ASGI обслуживает только /ws/* (см. island_bali/asgi.py, nginx/default.conf).
# HTTP API продолжает идти через gunicorn/WSGI — ASGI_APPLICATION нужен Channels
# для ProtocolTypeRouter и для тестов/runserver, не для production HTTP-трафика.
ASGI_APPLICATION = "island_bali.asgi.application"

# Отдельная логическая БД Redis для Channels (Celery уже занимает 0 — broker, 1 — result
# backend). Не поднимаем отдельный физический Redis — тот же контейнер, другой namespace.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env.str("CHANNELS_REDIS_URL", default="redis://redis:6379/2")],
        },
    },
}
# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",
#     }
# }

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

DATABASES = {
    'default': env.db()
}

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD")

# --- SMS (провайдер iqsms.ru / Rocket SMS) ---
SMS_LOGIN = env.str("SMS_LOGIN", default="")
SMS_PASSWORD = env.str("SMS_PASSWORD", default="")
# Имя отправителя должно быть заранее зарегистрировано у провайдера.
# Список доступных: GET https://api.iqsms.ru/messages/v2/senders.json
SMS_SENDER = env.str("SMS_SENDER", default="BiBipTrip")
SMS_API_URL = env.str(
    "SMS_API_URL", default="https://api.iqsms.ru/messages/v2/send.json"
)
SMS_TIMEOUT = env.int("SMS_TIMEOUT", default=10)
# Если False (или не заданы логин/пароль) — код только пишется в лог,
# реальная отправка не производится.
SMS_ENABLED = env.bool("SMS_ENABLED", default=True)
# Возвращать ли код подтверждения в теле HTTP-ответа.
# ВНИМАНИЕ: True полностью обесценивает подтверждение по SMS.
# Оставлено включённым для совместимости с текущим мобильным клиентом:
# выключить сразу после выката версии приложения, читающей код из SMS.
SMS_EXPOSE_CODE = env.bool("SMS_EXPOSE_CODE", default=True)
# Разрешать ли вход/регистрацию без ввода кода (старый контракт приложения).
# True — код в запросе необязателен, но если передан, он проверяется.
# False — код обязателен, вход без него запрещён.
SMS_ALLOW_LEGACY_AUTH = env.bool("SMS_ALLOW_LEGACY_AUTH", default=True)
# Время жизни кода подтверждения, секунд.
SMS_CODE_TTL = env.int("SMS_CODE_TTL", default=300)
# Минимальный интервал между запросами кода на один номер, секунд.
SMS_RESEND_INTERVAL = env.int("SMS_RESEND_INTERVAL", default=60)


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
        # M0 п.3.1: раньше AllowAny по умолчанию означало, что забытый
        # permission_classes на новой вьюхе тихо открывал её всему интернету.
        # Теперь по умолчанию требуется аутентификация; эндпоинты, которые
        # действительно должны быть публичными (логин, refresh/verify токена,
        # публичный каталог меню и т.п.), получают явный AllowAny точечно —
        # см. island_bali/urls.py и соответствующие views.py.
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "admin_login": env.str("ADMIN_LOGIN_THROTTLE_RATE", default="10/min"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        hours=env.int("ACCESS_TOKEN_LIFETIME_HOURS", 1)),
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
        hours=env.int("ACCESS_TOKEN_LIFETIME_HOURS", 1)),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(
        days=env.int("REFRESH_TOKEN_LIFETIME", 30)
    ),
}

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

GROUPS = {"owner": {}, "admin": {}, "moderator": {}, "support": {}, "employee": {}, "user": {}}

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



CELERY_BROKER_URL = env.str("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = env.str("CELERY_RESULT_BACKEND", default="redis://redis:6379/1")
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





# M1 п.22: структурированный лог переходов order/payment state (orders.state,
# orders.signals, orders.tasks, acquiring.providers) — без PII (см. docstring
# orders/services.py::_log_transition). Не переопределяет root/django loggers,
# чтобы не менять поведение остального проекта за пределами M0/M1.
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
    'loggers': {
        'orders.state': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'orders.signals': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'orders.tasks': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'acquiring.providers': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'acquiring.views': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        # M2/M3: WebSocket connection lifecycle и realtime event publication.
        # Как и остальные логгеры этого блока — без JWT/PII, только технические ID.
        'orders.consumers': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'orders.realtime': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'island_bali.ws_auth': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}



SSL_CERT_PATH = os.path.join(BASE_DIR, 'cert/9298136607.pem') 
SSL_KEY_PATH = os.path.join(BASE_DIR, 'cert/private.key')
CA_CERT_PATH = os.path.join(BASE_DIR, 'cert/chain-ecomm-ca-root-ca.crt')


ONESIGNAL_APP_ID = env.str("ONESIGNAL_APP_ID", default="")
ONESIGNAL_API_KEY = env.str("ONESIGNAL_API_KEY", default="")


LIFEPAY_CALLBACK_URL = 'https://example.com/api/orders/lifepay-callback/'
