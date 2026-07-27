"""Storage backends used by StudyBee.

The production backend uploads media files to Supabase Storage through its
S3-compatible API. Static files continue to be served by WhiteNoise.
"""

from urllib.parse import quote

from storages.backends.s3 import S3Storage


class SupabaseMediaStorage(S3Storage):
    """S3 storage with stable public URLs for a public Supabase bucket."""

    def __init__(self, *args, public_base_url="", **kwargs):
        self.public_base_url = public_base_url.rstrip("/")
        super().__init__(*args, **kwargs)

    def url(self, name, parameters=None, expire=None, http_method=None):
        if self.public_base_url:
            normalized_name = str(name).replace("\\", "/").lstrip("/")
            encoded_name = quote(normalized_name, safe="/~")
            return f"{self.public_base_url}/{encoded_name}"

        return super().url(
            name,
            parameters=parameters,
            expire=expire,
            http_method=http_method,
        )
