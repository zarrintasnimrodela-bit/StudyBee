"""
Django settings for the StudyBee project.

Production settings are intentionally secure by default. Local development
values can be placed in an uncommitted .env file in the project root.
"""

import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

TESTING = "test" in sys.argv

# Load local development variables without overriding real platform variables.
load_dotenv(BASE_DIR / ".env", override=False)


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def env_bool(name: str, default: bool = False) -> bool:
    """Read a strict boolean environment variable."""
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default

    normalized = raw_value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False

    raise ImproperlyConfigured(
        f"{name} must be one of: true, false, 1, 0, yes, no, on, off."
    )


def env_int(name: str, default: int) -> int:
    """Read a non-negative integer environment variable."""
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer.") from exc

    if value < 0:
        raise ImproperlyConfigured(f"{name} cannot be negative.")
    return value


def env_list(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable."""
    return [
        item.strip()
        for item in os.environ.get(name, default).split(",")
        if item.strip()
    ]


def append_unique(items: list[str], value: str | None) -> None:
    """Append a non-empty value once."""
    if value:
        cleaned = value.strip().rstrip("/")
        if cleaned and cleaned not in items:
            items.append(cleaned)


# ---------------------------------------------------------------------------
# Core security
# ---------------------------------------------------------------------------
# DEBUG is False unless explicitly enabled in the local .env file.
DEBUG = env_bool("DEBUG", default=False)

SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if DEBUG:
        # Keeps a first local run convenient without committing any key.
        # Add a persistent local SECRET_KEY to .env to keep sessions between
        # development-server restarts.
        SECRET_KEY = secrets.token_urlsafe(64)
    else:
        raise ImproperlyConfigured(
            "SECRET_KEY is required when DEBUG=False. Generate one and store "
            "it in the deployment platform's private environment variables."
        )

if not DEBUG and (
    len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-")
):
    raise ImproperlyConfigured(
        "Production SECRET_KEY must be at least 50 characters and must not "
        "start with 'django-insecure-'."
    )

local_hosts = "127.0.0.1,localhost,[::1]" if DEBUG else ""
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", local_hosts)

# Add exact hostnames supplied by common hosting platforms. This avoids using
# a broad wildcard while keeping the project portable.
platform_hosts = [
    os.environ.get("RAILWAY_PUBLIC_DOMAIN"),
    os.environ.get("RENDER_EXTERNAL_HOSTNAME"),
    os.environ.get("FLY_APP_NAME"),
]

for platform_host in platform_hosts:
    if platform_host:
        if platform_host == os.environ.get("FLY_APP_NAME"):
            platform_host = f"{platform_host}.fly.dev"
        append_unique(ALLOWED_HOSTS, platform_host)

if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS is required when DEBUG=False. Use a comma-separated "
        "list of exact deployment hostnames."
    )

local_origins = (
    "http://127.0.0.1:8000,http://localhost:8000" if DEBUG else ""
)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", local_origins)

for host in ALLOWED_HOSTS:
    # Wildcard host entries cannot be converted safely into exact origins.
    if host != "*" and not host.startswith("."):
        append_unique(CSRF_TRUSTED_ORIGINS, f"https://{host}")

for origin in CSRF_TRUSTED_ORIGINS:
    parsed_origin = urlparse(origin)
    if parsed_origin.scheme not in {"http", "https"} or not parsed_origin.netloc:
        raise ImproperlyConfigured(
            "Every CSRF_TRUSTED_ORIGINS value must be a complete http:// or "
            f"https:// origin. Invalid value: {origin!r}"
        )


# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "resources",
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
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
if TESTING:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
else:
    DATABASES = {
        "default": dj_database_url.config(
            default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
            conn_max_age=600,
        )
    }


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
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


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static and uploaded files
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

USE_CLOUD_STORAGE = env_bool("USE_CLOUD_STORAGE", default=False)

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": MEDIA_ROOT,
            "base_url": MEDIA_URL,
        },
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if TESTING
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

if USE_CLOUD_STORAGE:
    supabase_storage_settings = {
        "SUPABASE_S3_ACCESS_KEY_ID": os.environ.get(
            "SUPABASE_S3_ACCESS_KEY_ID"
        ),
        "SUPABASE_S3_SECRET_ACCESS_KEY": os.environ.get(
            "SUPABASE_S3_SECRET_ACCESS_KEY"
        ),
        "SUPABASE_S3_BUCKET_NAME": os.environ.get(
            "SUPABASE_S3_BUCKET_NAME"
        ),
        "SUPABASE_S3_ENDPOINT_URL": os.environ.get(
            "SUPABASE_S3_ENDPOINT_URL"
        ),
        "SUPABASE_S3_REGION": os.environ.get("SUPABASE_S3_REGION"),
        "SUPABASE_PUBLIC_MEDIA_URL": os.environ.get(
            "SUPABASE_PUBLIC_MEDIA_URL"
        ),
    }

    missing_storage_settings = [
        name
        for name, value in supabase_storage_settings.items()
        if not value
    ]

    if missing_storage_settings:
        raise ImproperlyConfigured(
            "Cloud storage is enabled, but these environment variables are "
            f"missing: {', '.join(missing_storage_settings)}"
        )

    public_media_url = supabase_storage_settings[
        "SUPABASE_PUBLIC_MEDIA_URL"
    ].rstrip("/")

    STORAGES["default"] = {
        "BACKEND": "config.storage_backends.SupabaseMediaStorage",
        "OPTIONS": {
            "access_key": supabase_storage_settings[
                "SUPABASE_S3_ACCESS_KEY_ID"
            ],
            "secret_key": supabase_storage_settings[
                "SUPABASE_S3_SECRET_ACCESS_KEY"
            ],
            "bucket_name": supabase_storage_settings[
                "SUPABASE_S3_BUCKET_NAME"
            ],
            "endpoint_url": supabase_storage_settings[
                "SUPABASE_S3_ENDPOINT_URL"
            ].rstrip("/"),
            "region_name": supabase_storage_settings[
                "SUPABASE_S3_REGION"
            ],
            "addressing_style": "path",
            "signature_version": "s3v4",
            "default_acl": None,
            "file_overwrite": False,
            "querystring_auth": False,
            "public_base_url": public_media_url,
        },
    }

    MEDIA_URL = f"{public_media_url}/"


# ---------------------------------------------------------------------------
# HTTPS, cookies, and response headers
# ---------------------------------------------------------------------------
# Hosted Django applications normally run behind a trusted reverse proxy.
# This setting allows Django to recognize the original HTTPS request.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", default=not DEBUG)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_HSTS_SECONDS = env_int(
    "SECURE_HSTS_SECONDS",
    default=3600 if not DEBUG else 0,
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", default=False)

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# SAMEORIGIN preserves local same-site document previews. External Supabase,
# Google Drive, and YouTube previews are not restricted by this response header.
X_FRAME_OPTIONS = "SAMEORIGIN"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
