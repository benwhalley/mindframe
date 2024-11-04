"""
Django settings for mindframe demo project.

"""

import os
import socket
from distutils.util import strtobool
from pathlib import Path
import dotenv
import environ
from types import SimpleNamespace


from magentic import OpenaiChatModel
from magentic.chat_model.litellm_chat_model import LitellmChatModel

import dj_database_url

dotenv.load_dotenv('.env')

print(os.environ)

import logging
logger = logging.getLogger(__name__)


env = environ.Env(
    DEBUG=(bool, False),
    DEBUG_EMAIL=(bool, False),
    DDT=(bool, False),
    SECRET_KEY=(str),
    COMPRESS_ENABLED=(bool, True),
    COMPRESS_OFFLINE=(bool, True),
    REDIS_URL=(str, "redis://localhost:6379/0"),
    ALLOWED_HOSTS=(str, "host.docker.internal,.localhost,127.0.0.1,[::1],dev.tickworks.com"),
    DEFAULT_FROM_EMAIL=(str, "admin@example.com"),
    CSRF_TRUSTED_ORIGINS=(str, "http://0.0.0.0"),
    EMAIL_PORT=(int, 587),
    EMAIL_HOST=(str),
    EMAIL_HOST_USER=(str),
    EMAIL_HOST_PASSWORD=(str),
    CELERY_TASK_ALWAYS_EAGER=(bool, False),
)

print("DEBUG: ", env("DEBUG"))

AUTH_USER_MODEL = "mindframe.CustomUser"


# Build paths inside the project like this: BASE_DIR / "subdir".
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")

# https://docs.djangoproject.com/en/5.0/ref/settings/#std:setting-ALLOWED_HOSTS
ALLOWED_HOSTS = list(map(str.strip, env("ALLOWED_HOSTS").split(",")))
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS").split(",")


EMAIL_HOST = env("EMAIL_HOST")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")


print(EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_PORT, DEFAULT_FROM_EMAIL)


# Application definitions
INSTALLED_APPS = [
    "mindframe",
    "debug_toolbar",
    "hijack",
    "dal",
    "dal_select2",
    # "compressor",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_extensions",
    "django.contrib.humanize",
    "whitenoise.runserver_nostatic",
    "crispy_forms",
    "crispy_bootstrap5",
    "rules.apps.AutodiscoverRulesConfig",
    "markdown_deux",
    "magiclink",
    "djmail",
    
]

MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "hijack.middleware.HijackUserMiddleware",
]

ROOT_URLCONF = "config.urls"

# Starting with Django 4.1+ we need to pick which template loaders to use
# based on our environment since 4.1+ will cache templates by default.
default_loaders = [
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
]

cached_loaders = [("django.template.loaders.cached.Loader", default_loaders)]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "loaders": default_loaders if DEBUG else cached_loaders,
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


DATABASES = {"default": dj_database_url.config()}


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",  # noqa: E501
    },
]

# Sessions
# https://docs.djangoproject.com/en/5.0/ref/settings/#sessions
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

# Redis
REDIS_URL = env("REDIS_URL")

# Caching
# https://docs.djangoproject.com/en/5.0/topics/cache/
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# Celery
# https://docs.celeryproject.org/en/stable/userguide/configuration.html
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_ALWAYS_EAGER = env('CELERY_TASK_ALWAYS_EAGER')

print(f"CELERY_TASK_ALWAYS_EAGER: {CELERY_TASK_ALWAYS_EAGER}")

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
]
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

COMPRESS_FILTERS = {
    "css": [
        "compressor.filters.css_default.CssAbsoluteFilter",
        "compressor.filters.cssmin.rCSSMinFilter",
        "compressor.filters.cssmin.CSSCompressorFilter",
        # "website.purgecss_filter.PurgeCSSFilter",
    ],
    "js": ["compressor.filters.jsmin.rJSMinFilter"],
}


COMPRESS_PRECOMPILERS = (("text/x-scss", "django_libsass.SassCompiler"),)
COMPRESS_ENABLED = env("COMPRESS_ENABLED")
COMPRESS_OFFLINE = env("COMPRESS_OFFLINE")
COMPRESS_ROOT = STATIC_ROOT

# Django Debug Toolbar
# https://django-debug-toolbar.readthedocs.io/
if DEBUG:
    # We need to configure an IP address to allow connections from, but in
    # Docker we can't use 127.0.0.1 since this runs in a container but we want
    # to access the toolbar from our browser outside of the container.
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS = [ip[: ip.rfind(".")] + ".1" for ip in ips] + [
        "127.0.0.1",
        "10.0.2.2",
    ]


AUTHENTICATION_BACKENDS = (
    "rules.permissions.ObjectPermissionBackend",
    "django.contrib.auth.backends.ModelBackend",
    "magiclink.backends.MagicLinkBackend",
)

LOGIN_URL = "magiclink:login"

MAGICLINK_REQUIRE_SAME_IP = False
# TODO: reduce to 3
MAGICLINK_TOKEN_USES = 5
MAGICLINK_REQUIRE_SAME_BROWSER = False
MAGICLINK_ANTISPAM_FORMS=False
# TODO: reduce to 1 hour
MAGICLINK_AUTH_TIMEOUT = 60 * 60 * 24 * 2  # 24 hours * X days
MAGICLINK_LOGIN_REQUEST_TIME_LIMIT = 30  # seconds
MAGICLINK_VERIFY_INCLUDE_EMAIL = False
MAGICLINK_ONE_TOKEN_PER_USER = True

MAGICLINK_LOGIN_TEMPLATE_NAME = "magiclink/login.html"
MAGICLINK_LOGIN_SENT_TEMPLATE_NAME = "magiclink/login_sent.html"
MAGICLINK_LOGIN_FAILED_TEMPLATE_NAME = "magiclink/login_failed.html"


EMAIL_BACKEND = "djmail.backends.async.EmailBackend"

if env("DEBUG_EMAIL"):
    DJMAIL_REAL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    DJMAIL_REAL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
print("DJMAIL_REAL_BACKEND is set to", DJMAIL_REAL_BACKEND)

STORAGES = {
    # "default": {
    #     "BACKEND": "storages.backends.s3.S3Storage",
    #     "OPTIONS": {
    #         "bucket_name": "practiceprogressuploads",
    #         "region_name": "lon1",
    #         "endpoint_url": "https://practiceprogressuploads.fra1.digitaloceanspaces.com",
    #         "access_key": env("DO_SPACES_ACCESS_KEY"),
    #         "secret_key": env("DO_SPACES_SECRET_KEY"),
    #         # default_acl will be private by default
    #     },
    # },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

CRISPY_TEMPLATE_PACK = "bootstrap5"


# EMAIL_BACKEND = "djmail.backends.celery.EmailBackend"
# DJMAIL_REAL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# if env("DEBUG_EMAIL"):
#     print("Using Console email backend")
#     DJMAIL_REAL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# else:
#     print("Using LIVE EMAIL BACKEND")
#     DJMAIL_REAL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"



LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",  # Ensure the root logger is set to debug level
    },
    "loggers": {
        "record": {
            "handlers": ["console"],
            "level": "INFO",  # Set logging level to DEBUG for the `record` app
            "propagate": False,  # Avoid propagating to the root logger to control output
        },
        "rules": {
            "handlers": ["console"],
            "level": "WARNING",  # Set logging level to DEBUG for the `record` app
            "propagate": False,  # Avoid propagating to the root logger to control output
        },
        "config": {
            "handlers": ["console"],
            "level": "WARNING",  # Set logging level to DEBUG for the `record` app
            "propagate": False,  # Avoid propagating to the root logger to control output
        },
        "django": {
            "handlers": ["console"],
            "level": "WARNING",  # Ensure Django's internal logs can also be debugged if needed
            "propagate": False,
        },
    },
}


# Set your database, middleware, and other settings

logger.debug("This is a debug message from the record app.")


DEBUG_TOOLBAR_PANELS = [
    # 'debug_toolbar.panels.history.HistoryPanel',
    # 'debug_toolbar.panels.versions.VersionsPanel',
    "debug_toolbar.panels.timer.TimerPanel",
    # 'debug_toolbar.panels.settings.SettingsPanel',
    # 'debug_toolbar.panels.headers.HeadersPanel',
    # 'debug_toolbar.panels.request.RequestPanel',
    "debug_toolbar.panels.sql.SQLPanel",
    # 'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    "debug_toolbar.panels.templates.TemplatesPanel",
    # 'debug_toolbar.panels.cache.CachePanel',
    # 'debug_toolbar.panels.signals.SignalsPanel',
    "debug_toolbar.panels.redirects.RedirectsPanel",
    "debug_toolbar.panels.profiling.ProfilingPanel",
]
DEBUG_TOOLBAR_CONFIG = {"ROOT_TAG_EXTRA_ATTRS": "hx-preserve"}

LOGIN_REDIRECT_URL = "/"


HIJACK_LOGIN_REDIRECT_URL = "/"
HIJACK_LOGOUT_REDIRECT_URL = "/"


MAGICLINK_EMAIL_STYLES = {
    'logo_url': 'https://psybot.llemma.net/static/logoplymouth.png',
    'background-colour': '#ffffff',
    'main-text-color': '#000000',
    'button-background-color': '#0078be',
    'button-text-color': '#ffffff',
}


MAGICLINK_EMAIL_SUBJECT = "Magic link to login to PsyBot"



# MINDFRAME SPECIFIC SETTINGS

MINDFRAME_AI_MODELS = SimpleNamespace(
    free=LitellmChatModel("ollama_chat/llama3.2", api_base="http://localhost:11434"),
    expensive=OpenaiChatModel("gpt-4o", api_type="azure"),
    cheap=OpenaiChatModel("gpt-4o-mini", api_type="azure")
)