# Supabase Storage setup for StudyBee

StudyBee keeps using the local `media/` folder during development. On the
production host, it can upload resource files to a public Supabase Storage
bucket through Supabase's S3-compatible endpoint.

## 1. Create the storage bucket

1. Open your Supabase project.
2. Go to **Storage**.
3. Create a bucket named `studybee-resources`.
4. Make the bucket **public**. StudyBee's resources are intended to be opened
   and shared by students, so the public bucket provides stable links.
5. Keep the bucket name exactly the same as
   `SUPABASE_S3_BUCKET_NAME`, or update the environment variable to match.

## 2. Enable S3 access

1. Go to **Storage → Configuration → S3**.
2. Enable the S3 protocol.
3. Generate an S3 access key and secret key.
4. Copy the access key, secret key, endpoint, and region immediately. The
   secret key should be treated like a password and must never be committed to
   GitHub.

Supabase normally shows an endpoint in this form:

```text
https://YOUR_PROJECT_REF.storage.supabase.co/storage/v1/s3
```

## 3. Add production environment variables

Add these variables to the service that runs Django:

```env
USE_CLOUD_STORAGE=True
SUPABASE_S3_ACCESS_KEY_ID=your_access_key
SUPABASE_S3_SECRET_ACCESS_KEY=your_secret_key
SUPABASE_S3_BUCKET_NAME=studybee-resources
SUPABASE_S3_ENDPOINT_URL=https://YOUR_PROJECT_REF.storage.supabase.co/storage/v1/s3
SUPABASE_S3_REGION=your_project_region
SUPABASE_PUBLIC_MEDIA_URL=https://YOUR_PROJECT_REF.supabase.co/storage/v1/object/public/studybee-resources
```

Use the exact endpoint and region shown in your Supabase dashboard.

## 4. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

The requirements now include `django-storages` with its S3 dependencies.

## 5. Test locally without cloud storage

Leave this setting as follows:

```env
USE_CLOUD_STORAGE=False
```

Django will continue to store files in the local `media/` directory.

## 6. Test the production connection

After adding the production variables and deploying:

1. Open Django Admin.
2. Add a small test resource file.
3. Open the resource from the public course page.
4. Confirm its URL starts with your `SUPABASE_PUBLIC_MEDIA_URL`.
5. Confirm the file appears in the Supabase bucket.

## Existing Railway uploads

Changing the storage backend does not automatically copy the old files from
Railway. When those files are recovered, upload them to the Supabase bucket
while preserving their stored relative paths, such as:

```text
resources/example.pdf
resources/solutions/example-solution.pdf
```

The corresponding database `file` values can then continue to reference those
relative paths.
