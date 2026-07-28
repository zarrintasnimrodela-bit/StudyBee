import re

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import resources.validators
from django.utils import timezone


def populate_structured_semester(apps, schema_editor):
    Resource = apps.get_model("resources", "Resource")

    verified_time = timezone.now()

    for resource in Resource.objects.all().iterator():
        update_fields = [
            "verification_status",
            "verified_at",
        ]
        resource.verification_status = "VERIFIED"
        resource.verified_at = verified_time

        match = re.match(
            r"^\s*(spring|summer|fall)\s+(\d{4})\s*$",
            resource.semester or "",
            flags=re.IGNORECASE,
        )

        if match:
            resource.semester_term = match.group(1).upper()
            resource.semester_year = int(match.group(2))
            update_fields.extend(
                [
                    "semester_term",
                    "semester_year",
                ]
            )

        resource.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(
            settings.AUTH_USER_MODEL
        ),
        ("resources", "0014_resource_solution_file_resource_solution_link"),
    ]

    operations = [
        migrations.AlterField(
            model_name="resource",
            name="file",
            field=models.FileField(
                blank=True,
                help_text=(
                    "Upload file here if you want to store "
                    "the file directly."
                ),
                null=True,
                upload_to="resources/",
                validators=[
                    resources.validators.validate_resource_file
                ],
            ),
        ),
        migrations.AlterField(
            model_name="resource",
            name="solution_file",
            field=models.FileField(
                blank=True,
                help_text=(
                    "Optional. Upload solution/answer file only "
                    "for question resources."
                ),
                null=True,
                upload_to="resources/solutions/",
                validators=[
                    resources.validators.validate_resource_file
                ],
            ),
        ),
        migrations.AddField(
            model_name="resource",
            name="semester_term",
            field=models.CharField(
                blank=True,
                choices=[
                    ("SPRING", "Spring"),
                    ("SUMMER", "Summer"),
                    ("FALL", "Fall"),
                ],
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="resource",
            name="semester_year",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(
                        2000
                    ),
                    django.core.validators.MaxValueValidator(
                        2100
                    ),
                ],
            ),
        ),
        migrations.AddField(
            model_name="resource",
            name="verification_status",
            field=models.CharField(
                choices=[
                    ("UNVERIFIED", "Unverified"),
                    ("VERIFIED", "Verified"),
                    ("NEEDS_REVIEW", "Needs review"),
                    ("BROKEN", "Broken"),
                ],
                db_index=True,
                default="UNVERIFIED",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="resource",
            name="verified_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="resource",
            name="verified_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="verified_resources",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="reportissue",
            name="resource",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="issue_reports",
                to="resources.resource",
            ),
        ),
        migrations.CreateModel(
            name="ResourceSubmission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "title",
                    models.CharField(max_length=200),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("SLIDE", "Slides"),
                            ("NOTE", "Notes"),
                            ("QUESTION", "Questions"),
                            ("LAB", "Lab Files"),
                            ("VIDEO", "Videos"),
                            ("BOOK", "Books"),
                            ("LINK", "Useful Links"),
                            ("OTHER", "Other"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "exam_part",
                    models.CharField(
                        choices=[
                            ("MIDTERM", "Midterm"),
                            ("FINAL", "Final"),
                            ("GENERAL", "General"),
                        ],
                        default="GENERAL",
                        max_length=20,
                        verbose_name="Syllabus",
                    ),
                ),
                (
                    "question_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("PAST_EXAM", "Past Exam"),
                            ("ASSIGNMENT", "Assignment"),
                            ("QUIZ", "Quiz"),
                            ("PRACTICE", "Practice"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "description",
                    models.TextField(blank=True),
                ),
                (
                    "file",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="submissions/resources/",
                        validators=[
                            resources.validators.validate_resource_file
                        ],
                    ),
                ),
                (
                    "external_link",
                    models.URLField(blank=True),
                ),
                (
                    "solution_file",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="submissions/solutions/",
                        validators=[
                            resources.validators.validate_resource_file
                        ],
                    ),
                ),
                (
                    "solution_link",
                    models.URLField(blank=True),
                ),
                (
                    "semester_term",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("SPRING", "Spring"),
                            ("SUMMER", "Summer"),
                            ("FALL", "Fall"),
                        ],
                        max_length=10,
                    ),
                ),
                (
                    "semester_year",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(
                                2000
                            ),
                            django.core.validators.MaxValueValidator(
                                2100
                            ),
                        ],
                    ),
                ),
                (
                    "submitter_name",
                    models.CharField(
                        blank=True,
                        max_length=120,
                    ),
                ),
                (
                    "submitter_email",
                    models.EmailField(
                        blank=True,
                        max_length=254,
                    ),
                ),
                (
                    "note_to_admin",
                    models.TextField(blank=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("APPROVED", "Approved"),
                            ("REJECTED", "Rejected"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                (
                    "review_notes",
                    models.TextField(blank=True),
                ),
                (
                    "reviewed_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "submitted_at",
                    models.DateTimeField(
                        auto_now_add=True,
                    ),
                ),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="resource_submissions",
                        to="resources.course",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_resource_submissions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-submitted_at"],
            },
        ),
        migrations.AddIndex(
            model_name="resource",
            index=models.Index(
                fields=[
                    "semester_term",
                    "semester_year",
                ],
                name="resource_semester_idx",
            ),
        ),
        migrations.RunPython(
            populate_structured_semester,
            migrations.RunPython.noop,
        ),
    ]
