# StudyBee Render Deployment

Files:
- `render.yaml`: Render Blueprint for a free Python web service in Singapore.
- `build.sh`: installs dependencies, collects static files, and applies migrations.

During Blueprint creation, Render will ask for:
- `DATABASE_URL`
- `SUPABASE_S3_ACCESS_KEY_ID`
- `SUPABASE_S3_SECRET_ACCESS_KEY`

Use the values from the local `.env` file. Do not commit or share `.env`.
