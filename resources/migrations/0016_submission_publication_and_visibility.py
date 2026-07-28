import django.db.models.deletion
from django.db import migrations, models


def repair_approved_submissions(apps, schema_editor):
    ResourceSubmission = apps.get_model(
        "resources",
        "ResourceSubmission",
    )
    Resource = apps.get_model(
        "resources",
        "Resource",
    )

    for submission in ResourceSubmission.objects.filter(
        status="APPROVED",
        published_resource__isnull=True,
    ).iterator():
        candidates = Resource.objects.filter(
            course_id=submission.course_id,
            title__iexact=submission.title,
        )

        if submission.external_link:
            candidates = candidates.filter(
                external_link=submission.external_link
            )
        elif submission.file:
            candidates = candidates.filter(
                file=submission.file.name
            )
        else:
            candidates = Resource.objects.none()

        resource = candidates.order_by("id").first()

        if resource is None:
            resource = Resource.objects.create(
                course_id=submission.course_id,
                title=submission.title,
                category=submission.category,
                exam_part=submission.exam_part,
                question_type=submission.question_type,
                description=submission.description,
                file=(
                    submission.file.name
                    if submission.file
                    else ""
                ),
                external_link=submission.external_link,
                solution_file=(
                    submission.solution_file.name
                    if submission.solution_file
                    else ""
                ),
                solution_link=submission.solution_link,
                semester_term=submission.semester_term,
                semester_year=submission.semester_year,
                verification_status="UNVERIFIED",
            )
        else:
            Resource.objects.filter(pk=resource.pk).update(
                verification_status="UNVERIFIED",
                verified_by=None,
                verified_at=None,
            )

        submission.published_resource_id = resource.pk
        submission.save(
            update_fields=["published_resource"]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0015_studybee_features"),
    ]

    operations = [
        migrations.AddField(
            model_name="resourcesubmission",
            name="published_resource",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="source_submission",
                to="resources.resource",
            ),
        ),
        migrations.RunPython(
            repair_approved_submissions,
            migrations.RunPython.noop,
        ),
    ]
