from pathlib import PurePath, PureWindowsPath

from django.core.exceptions import ValidationError


MAX_FILE_SIZE = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
}


def sanitize_filename(filename):
    """Return a safe basename for Windows-style or POSIX-style paths."""
    windows_name = PureWindowsPath(str(filename)).name
    return PurePath(windows_name).name


def validate_resource_file(uploaded_file):
    if not uploaded_file:
        return

    safe_name = sanitize_filename(uploaded_file.name)
    extension = PurePath(safe_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(
            extension.lstrip(".").upper()
            for extension in sorted(ALLOWED_EXTENSIONS)
        )
        raise ValidationError(
            f"Unsupported file type. Allowed: {allowed}."
        )

    file_size = getattr(uploaded_file, "size", 0)

    if file_size > MAX_FILE_SIZE:
        raise ValidationError(
            "File is too large. Maximum allowed size is 50 MB."
        )
