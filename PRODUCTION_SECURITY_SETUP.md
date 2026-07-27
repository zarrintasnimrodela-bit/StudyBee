# StudyBee production security setup

## Local development

1. Copy `.env.example` to `.env`:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Generate a persistent local secret key:

   ```powershell
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

3. Paste the generated value after `SECRET_KEY=` in `.env`.

4. Install dependencies and check the project:

   ```powershell
   python -m pip install -r requirements.txt
   python manage.py check
   python manage.py runserver
   ```

The real `.env` file must remain ignored by Git.

## Production environment variables

Set these as private variables in the hosting platform:

```text
DEBUG=False
SECRET_KEY=<unique random value of at least 50 characters>
ALLOWED_HOSTS=<exact deployed hostname>
CSRF_TRUSTED_ORIGINS=https://<exact deployed hostname>
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=3600
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
```

Do not include `https://` in `ALLOWED_HOSTS`. Do include it in
`CSRF_TRUSTED_ORIGINS`. Multiple values are comma-separated.

The application also recognizes exact hostnames supplied by Railway, Render,
and Fly.io environment variables, but explicitly setting `ALLOWED_HOSTS` and
`CSRF_TRUSTED_ORIGINS` remains clearer and safer.

## Generate the production secret key

Run locally:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output into the hosting platform's private `SECRET_KEY` variable.
Never put it in GitHub, screenshots, documentation, or chat.

## HTTPS and HSTS rollout

Production redirects HTTP to HTTPS and uses secure session/CSRF cookies.
`SECURE_HSTS_SECONDS` starts at one hour. After the deployed HTTPS site has
worked correctly for several days, it can be raised gradually, for example to
`2592000` (30 days), then `31536000` (one year).

Do not enable `SECURE_HSTS_INCLUDE_SUBDOMAINS` or `SECURE_HSTS_PRELOAD` until
you control every subdomain and understand that browsers may remember the
HTTPS-only policy for a long time.

## Deployment check

Run this with production-like environment variables:

```powershell
python manage.py check --deploy
```

One warning about `X_FRAME_OPTIONS` may remain intentionally because StudyBee
uses `SAMEORIGIN` for local same-site document previews rather than `DENY`.
