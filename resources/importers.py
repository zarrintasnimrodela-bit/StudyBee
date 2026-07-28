import csv
import io

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    Course,
    Resource,
    SEMESTER_TERM_CHOICES,
)


class BulkImportError(Exception):
    pass


def _choice_code(value, choices, field_name, default=""):
    cleaned = (value or "").strip()

    if not cleaned:
        return default

    normalized = cleaned.upper().replace(" ", "_")
    by_code = {code.upper(): code for code, _label in choices}
    by_label = {
        label.upper().replace(" ", "_"): code
        for code, label in choices
    }

    if normalized in by_code:
        return by_code[normalized]

    if normalized in by_label:
        return by_label[normalized]

    allowed = ", ".join(label for _code, label in choices)
    raise BulkImportError(
        f"Invalid {field_name} '{cleaned}'. Allowed: {allowed}."
    )


def _year(value, row_number):
    cleaned = (value or "").strip()

    if not cleaned:
        return None

    try:
        year = int(cleaned)
    except ValueError as exc:
        raise BulkImportError(
            f"Row {row_number}: semester_year must be a number."
        ) from exc

    if year < 2000 or year > 2100:
        raise BulkImportError(
            f"Row {row_number}: semester_year must be 2000–2100."
        )

    return year


@transaction.atomic
def import_resources_from_csv(uploaded_file, user=None):
    try:
        raw = uploaded_file.read()
        text = raw.decode("utf-8-sig")
    except (AttributeError, UnicodeDecodeError) as exc:
        raise BulkImportError(
            "The CSV must be UTF-8 encoded."
        ) from exc

    reader = csv.DictReader(io.StringIO(text))

    required_headers = {
        "course_code",
        "course_title",
        "title",
        "category",
        "external_link",
    }

    actual_headers = set(reader.fieldnames or [])
    missing_headers = sorted(required_headers - actual_headers)

    if missing_headers:
        raise BulkImportError(
            "Missing required CSV columns: "
            + ", ".join(missing_headers)
        )

    created_courses = 0
    created_resources = 0
    updated_resources = 0
    processed_rows = 0

    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue

        processed_rows += 1
        course_code = (row.get("course_code") or "").strip().upper()
        course_title = (row.get("course_title") or "").strip()
        title = (row.get("title") or "").strip()
        external_link = (row.get("external_link") or "").strip()

        if not course_code or not course_title or not title:
            raise BulkImportError(
                f"Row {row_number}: course_code, course_title, "
                "and title are required."
            )

        if not external_link:
            raise BulkImportError(
                f"Row {row_number}: external_link is required "
                "for CSV imports."
            )

        course, course_created = Course.objects.get_or_create(
            course_code=course_code,
            defaults={
                "course_title": course_title,
                "description": (
                    row.get("course_description") or ""
                ).strip(),
                "hard_prerequisite": (
                    row.get("hard_prerequisite") or ""
                ).strip(),
                "soft_prerequisite": (
                    row.get("soft_prerequisite") or ""
                ).strip(),
                "lab_type": _choice_code(
                    row.get("lab_type"),
                    Course.LAB_TYPE_CHOICES,
                    "lab_type",
                    default="NO_LAB",
                ),
            },
        )

        if course_created:
            created_courses += 1
        else:
            changed = False

            if course.course_title != course_title:
                course.course_title = course_title
                changed = True

            for field_name in (
                "course_description",
                "hard_prerequisite",
                "soft_prerequisite",
            ):
                csv_value = (row.get(field_name) or "").strip()

                if not csv_value:
                    continue

                model_field = (
                    "description"
                    if field_name == "course_description"
                    else field_name
                )

                if getattr(course, model_field) != csv_value:
                    setattr(course, model_field, csv_value)
                    changed = True

            if changed:
                course.save()

        category = _choice_code(
            row.get("category"),
            Resource.CATEGORY_CHOICES,
            "category",
        )
        exam_part = _choice_code(
            row.get("exam_part"),
            Resource.SYLLABUS_CHOICES,
            "exam_part",
            default="GENERAL",
        )
        question_type = _choice_code(
            row.get("question_type"),
            Resource.QUESTION_TYPE_CHOICES,
            "question_type",
            default="",
        )
        semester_term = _choice_code(
            row.get("semester_term"),
            SEMESTER_TERM_CHOICES,
            "semester_term",
            default="",
        )
        verification_status = _choice_code(
            row.get("verification_status"),
            Resource.VERIFICATION_CHOICES,
            "verification_status",
            default="UNVERIFIED",
        )
        semester_year = _year(
            row.get("semester_year"),
            row_number,
        )

        if bool(semester_term) != bool(semester_year):
            raise BulkImportError(
                f"Row {row_number}: provide both semester_term "
                "and semester_year, or neither."
            )

        existing = Resource.objects.filter(
            course=course,
            title__iexact=title,
        ).order_by("id").first()

        resource = existing or Resource(
            course=course,
            title=title,
        )

        resource.category = category
        resource.exam_part = exam_part
        resource.question_type = question_type
        resource.description = (
            row.get("description") or ""
        ).strip()
        resource.external_link = external_link
        resource.solution_link = (
            row.get("solution_link") or ""
        ).strip()
        resource.semester_term = semester_term
        resource.semester_year = semester_year
        resource.verification_status = verification_status

        if verification_status == "VERIFIED":
            resource.verified_by = user

        try:
            resource.save()
        except ValidationError as exc:
            raise BulkImportError(
                f"Row {row_number}: {exc}"
            ) from exc

        if existing:
            updated_resources += 1
        else:
            created_resources += 1

    if processed_rows == 0:
        raise BulkImportError(
            "The CSV did not contain any resource rows."
        )

    return {
        "processed_rows": processed_rows,
        "created_courses": created_courses,
        "created_resources": created_resources,
        "updated_resources": updated_resources,
    }
