from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("resources", "0018_student_email_otp_and_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailverificationcode",
            name="purpose",
            field=models.CharField(
                choices=[
                    ("SIGNUP", "Sign up"),
                    ("PASSWORD_RESET", "Password reset"),
                ],
                db_index=True,
                default="SIGNUP",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="emailverificationcode",
            index=models.Index(
                fields=["email", "purpose", "created_at"],
                name="otp_email_purpose_idx",
            ),
        ),
    ]
