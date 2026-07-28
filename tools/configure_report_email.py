from pathlib import Path


SETTINGS_MARKER = "# StudyBee report-resolution email"
RENDER_MARKER = "      - key: EMAIL_HOST"


settings_path = Path("config/settings.py")
settings_text = settings_path.read_text(encoding="utf-8")

email_settings = r'''

# StudyBee report-resolution email
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "False") == "True"
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "StudyBee <noreply@localhost>",
)
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    (
        "django.core.mail.backends.smtp.EmailBackend"
        if EMAIL_HOST and EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
        else "django.core.mail.backends.console.EmailBackend"
    ),
)
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "20"))
'''

if SETTINGS_MARKER not in settings_text:
    settings_path.write_text(
        settings_text.rstrip() + email_settings + "\n",
        encoding="utf-8",
    )
    print("Added email settings to config/settings.py")
else:
    print("Email settings already exist in config/settings.py")

render_path = Path("render.yaml")

if render_path.exists():
    render_text = render_path.read_text(encoding="utf-8")

    render_vars = '''
      - key: EMAIL_HOST
        value: smtp.gmail.com

      - key: EMAIL_PORT
        value: "587"

      - key: EMAIL_HOST_USER
        sync: false

      - key: EMAIL_HOST_PASSWORD
        sync: false

      - key: EMAIL_USE_TLS
        value: "True"

      - key: DEFAULT_FROM_EMAIL
        sync: false
'''

    if RENDER_MARKER not in render_text:
        anchor = "      - key: DATABASE_URL\n        sync: false\n"

        if anchor not in render_text:
            raise SystemExit(
                "Could not find DATABASE_URL in render.yaml. "
                "Email variables were not added."
            )

        render_text = render_text.replace(
            anchor,
            anchor + render_vars,
            1,
        )
        render_path.write_text(render_text, encoding="utf-8")
        print("Added email variables to render.yaml")
    else:
        print("Email variables already exist in render.yaml")
else:
    print("render.yaml was not found; skipped Render configuration")
