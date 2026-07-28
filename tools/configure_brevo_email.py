from pathlib import Path
import re


SETTINGS_PATH = Path("config/settings.py")
RENDER_PATH = Path("render.yaml")
SETTINGS_MARKER = "# StudyBee Brevo transactional email"

settings_text = SETTINGS_PATH.read_text(encoding="utf-8")

brevo_settings = '''
# StudyBee Brevo transactional email
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.environ.get(
    "BREVO_SENDER_EMAIL",
    "",
)
BREVO_SENDER_NAME = os.environ.get(
    "BREVO_SENDER_NAME",
    "StudyBee",
)
'''

if SETTINGS_MARKER not in settings_text:
    SETTINGS_PATH.write_text(
        settings_text.rstrip() + "\n\n" + brevo_settings + "\n",
        encoding="utf-8",
    )
    print("Added Brevo settings to config/settings.py")
else:
    print("Brevo settings already exist in config/settings.py")

if not RENDER_PATH.exists():
    print("render.yaml was not found; skipped Render configuration")
    raise SystemExit(0)

render_text = RENDER_PATH.read_text(encoding="utf-8")

old_email_keys = [
    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
    "EMAIL_USE_TLS",
    "EMAIL_USE_SSL",
    "DEFAULT_FROM_EMAIL",
]

for key in old_email_keys:
    pattern = re.compile(
        rf"\n      - key: {re.escape(key)}\n"
        rf"(?:(?!\n      - key: ).)*",
        re.DOTALL,
    )
    render_text = pattern.sub("", render_text)

if "      - key: BREVO_API_KEY\n" not in render_text:
    anchor = "      - key: DATABASE_URL\n        sync: false\n"

    if anchor not in render_text:
        raise SystemExit(
            "Could not find DATABASE_URL in render.yaml."
        )

    brevo_vars = '''
      - key: BREVO_API_KEY
        sync: false

      - key: BREVO_SENDER_EMAIL
        sync: false

      - key: BREVO_SENDER_NAME
        value: StudyBee
'''

    render_text = render_text.replace(
        anchor,
        anchor + brevo_vars,
        1,
    )

RENDER_PATH.write_text(
    render_text,
    encoding="utf-8",
)

print("Configured render.yaml for Brevo HTTPS email delivery")
