# Step 1 completed: Supabase cloud file storage

This version adds:

- Local `media/` storage for development.
- Supabase Storage through its S3-compatible API for production.
- Stable public Supabase URLs for resource and solution files.
- Environment-variable validation when cloud storage is enabled.
- Duplicate filename protection (`file_overwrite=False`).
- Correct copy-link behavior for absolute cloud URLs.
- Local-only Django media serving while in development.
- UTF-8 `requirements.txt` with `django-storages[s3]`.
- `.env.example` and detailed Supabase setup instructions.

No model or database migration is required for this step.
