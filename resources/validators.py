import os
from pathlib import Path
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

def validate_resource_file(file):
    ext = Path(file.name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            "Unsupported file type. Allowed: PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX, ZIP, PNG, JPG."
        )

    if file.size > MAX_FILE_SIZE:
        raise ValidationError(
            "File size exceeds the 50 MB limit."
        )

def sanitize_filename(filename):
    name = os.path.basename(filename)
    return name.replace("..", "").replace("/", "").replace("\\", "")