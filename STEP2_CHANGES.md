# Step 2 changes — production security

- Removed the committed production secret-key fallback.
- Added optional local `.env` loading through `python-dotenv`.
- Made `DEBUG=False` the default.
- Added strict environment-variable parsing and validation.
- Required a strong production `SECRET_KEY` and non-empty `ALLOWED_HOSTS`.
- Added exact common-platform hostname support without broad wildcards.
- Validated `CSRF_TRUSTED_ORIGINS` values.
- Enabled production HTTPS redirect and secure session/CSRF cookies.
- Added a cautious one-hour HSTS starting value for production.
- Added modern response security headers.
- Preserved local same-origin document previews.
- Added setup and deployment-check documentation.
