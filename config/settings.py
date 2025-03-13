import logging
import os
import socket
from distutils.util import strtobool
from pathlib import Path

import dj_database_url
from decouple import Csv, config
from langfuse.callback import CallbackHandler

logger = logging.getLogger(__name__)

REDIS_URL = config("REDIS_URL", default="redis://redis:6379/0")
CHAT_URL = config("CHAT_URL", default=None)
WEB_URL = config("WEB_URL", default=None)

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default=".llemma.net,localhost,127.0.0.1",
    cast=Csv(),
)


SESSION_ENGINE = "django.contrib.sessions.backends.cache"  # use Redis
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = 60 * 60 * 24  # 1 day in seconds
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Keep session even if browser closes

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="https://*.llemma.net,http://localhost,http://127.0.0.1",
    cast=Csv(),
)

DEBUG = config("DEBUG", default=False, cast=bool)
DDT = config("DDT", default=False, cast=bool)
DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: DDT,  # This disables the toolbar by default
}


SECRET_KEY = config("SECRET_KEY")
COMPRESS_ENABLED = config("COMPRESS_ENABLED", default=True, cast=bool)
COMPRESS_OFFLINE = config("COMPRESS_OFFLINE", default=True, cast=bool)

EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST = config("EMAIL_HOST", default=None)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default=None)
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default=None)
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="admin@example.com")

EMAIL_BACKEND = "djmail.backends.async.EmailBackend"
DEBUG_EMAIL = config("DEBUG_EMAIL", default=False, cast=bool)
if DEBUG_EMAIL:
    DJMAIL_REAL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    DJMAIL_REAL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

logger.info("DJMAIL_REAL_BACKEND is set to", DJMAIL_REAL_BACKEND)


langfuse_handler = CallbackHandler()
# logger.info("Langfuse auth: ", langfuse_handler.auth_check())

# Build paths inside the project like this: BASE_DIR / "subdir".
BASE_DIR = Path(__file__).resolve().parent.parent

# Application definitions
INSTALLED_APPS = [
    "llmtools",
    "mindframe",
    "treebeard",
    "debug_toolbar",
    "hijack",
    "crispy_forms",
    "crispy_bootstrap5",
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
    "rules.apps.AutodiscoverRulesConfig",
    # "magiclink",
    "djmail",
    "django_celery_beat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "hijack.middleware.HijackUserMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

ROOT_URLCONF = "config.urls"

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

DATABASE_URL = config("DATABASE_URL", default=None)
DATABASES = {"default": dj_database_url.config(default=DATABASE_URL)}
logger.info("DATABASE SETTINGS:", str(DATABASE_URL), str(DATABASES))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


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


CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# https://docs.celeryproject.org/en/stable/userguide/configuration.html
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=False, cast=bool)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"

LANGUAGE_CODE = config("LANGUAGE_CODE", default="en-gb")
TIME_ZONE = config("TIME_ZONE", default="UTC")
USE_I18N = True
USE_L10N = True
USE_TZ = True

# STATIC FILES
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
    ],
    "js": ["compressor.filters.jsmin.rJSMinFilter"],
}

COMPRESS_PRECOMPILERS = (("text/x-scss", "django_libsass.SassCompiler"),)
COMPRESS_ENABLED = config("COMPRESS_ENABLED", default=False, cast=bool)
COMPRESS_OFFLINE = config("COMPRESS_OFFLINE", default=False, cast=bool)
COMPRESS_ROOT = STATIC_ROOT


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
    # "magiclink.backends.MagicLinkBackend",
)

LOGIN_URL = "admin:index"


# MAGICLINK_REQUIRE_SAME_IP = False
# MAGICLINK_TOKEN_USES = config("MAGICLINK_TOKEN_USES", default=5, cast=int)
# MAGICLINK_REQUIRE_SAME_BROWSER = config("MAGICLINK_REQUIRE_SAME_BROWSER", default=False, cast=bool)
# MAGICLINK_ANTISPAM_FORMS = False
# MAGICLINK_AUTH_TIMEOUT = config(
#     "MAGICLINK_AUTH_TIMEOUT", default=60 * 60 * 24 * 2, cast=int
# )  # 24 hours * X days
# MAGICLINK_LOGIN_REQUEST_TIME_LIMIT = config(
#     "MAGICLINK_LOGIN_REQUEST_TIME_LIMIT", default=30, cast=int
# )  # 24 hours
# MAGICLINK_VERIFY_INCLUDE_EMAIL = False
# MAGICLINK_ONE_TOKEN_PER_USER = True
# MAGICLINK_LOGIN_TEMPLATE_NAME = "magiclink/login.html"
# MAGICLINK_LOGIN_SENT_TEMPLATE_NAME = "magiclink/login_sent.html"
# MAGICLINK_LOGIN_FAILED_TEMPLATE_NAME = "magiclink/login_failed.html"


STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


class LogModuleFilter(logging.Filter):
    def filter(self, record):
        # Add the logger name to the message
        record.msg = f"{record.name}: {record.msg}"
        return True


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "detailed": {
            "format": (
                "%(asctime)s [%(levelname)s] "
                "%(name)s (%(module)s:%(funcName)s:%(lineno)d) - %(message)s"
            ),
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "detailed",
            "stream": "ext://sys.stderr",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}


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

LOGIN_REDIRECT_URL = "/"
HIJACK_LOGIN_REDIRECT_URL = "/"
HIJACK_LOGOUT_REDIRECT_URL = "/"

MAGICLINK_EMAIL_STYLES = {
    "logo_url": "https://psybot.llemma.net/static/logoplymouth.png",
    "background-colour": "#ffffff",
    "main-text-color": "#000000",
    "button-background-color": "#0078be",
    "button-text-color": "#ffffff",
}

MAGICLINK_EMAIL_SUBJECT = config(
    "MAGICLINK_EMAIL_SUBJECT", default="Magic link to login to Mindframe"
)

SHELL_PLUS = "ipython"
AUTH_USER_MODEL = "mindframe.CustomUser"
