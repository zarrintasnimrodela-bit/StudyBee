from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        (
            "resources",
            "0016_submission_publication_and_visibility",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="reportissue",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("CHECKED", "Checked"),
                    ("RESOLVED", "Resolved"),
                ],
                db_index=True,
                default="PENDING",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="reportissue",
            name="admin_response",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Optional message included in the reporter email. "
                    "A default message is used when this is blank."
                ),
            ),
        ),
        migrations.AddField(
            model_name="reportissue",
            name="notification_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="reportissue",
            name="notification_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reportissue",
            name="resolution",
            field=models.CharField(
                blank=True,
                choices=[
                    (
                        "REPUBLISHED",
                        "Issue fixed — resource republished",
                    ),
                    (
                        "REMOVED",
                        "Resource removed from the public site",
                    ),
                    (
                        "DISMISSED",
                        "Report dismissed — resource republished",
                    ),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="reportissue",
            name="resolved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reportissue",
            name="resolved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="resolved_resource_reports",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
