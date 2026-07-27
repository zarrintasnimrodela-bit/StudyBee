# Upload Security Setup

Connect the validator to your Resource model fields:

file = models.FileField(
    upload_to='resources/',
    validators=[validate_resource_file]
)

solution_file = models.FileField(
    upload_to='resources/solutions/',
    validators=[validate_resource_file]
)

Import:

from .validators import validate_resource_file

Run:

python manage.py check