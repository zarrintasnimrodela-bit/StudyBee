from django.db import models
from django.core.exceptions import ValidationError


class Course(models.Model):
    LAB_TYPE_CHOICES = [
        ('NO_LAB', 'No Lab'),
        ('WEEKLY', 'Weekly Lab'),
        ('BIWEEKLY', 'Biweekly Lab'),
    ]

    course_code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Example: CSE421, CSE370, CSE220"
    )

    course_title = models.CharField(
        max_length=200,
        help_text="Example: Computer Networks, Database Systems"
    )

    description = models.TextField(
        blank=True,
        help_text="Short description shown on the course page."
    )

    hard_prerequisite = models.CharField(
        max_length=250,
        blank=True,
        help_text="Example: CSE220, CSE221. Leave empty if there is no hard prerequisite."
)

    soft_prerequisite = models.CharField(
        max_length=250,
        blank=True,
        help_text="Example: CSE370. Optional course that helps but is not mandatory."
)

    lab_type = models.CharField(
        max_length=20,
        choices=LAB_TYPE_CHOICES,
        default='NO_LAB',
        help_text="Select lab type for this course."
    )

    def __str__(self):
        return f"{self.course_code} - {self.course_title}"


class Resource(models.Model):
    CATEGORY_CHOICES = [
        ('SLIDE', 'Slides'),
        ('NOTE', 'Notes'),
        ('QUESTION', 'Questions'),
        ('LAB', 'Lab Files'),
        ('VIDEO', 'Videos'),
        ('BOOK', 'Books'),
        ('LINK', 'Useful Links'),
        ('OTHER', 'Other'),
    ]

    QUESTION_TYPE_CHOICES = [
        ('PAST_EXAM', 'Past Exam'),
        ('ASSIGNMENT', 'Assignment'),
        ('QUIZ', 'Quiz'),
        ('PRACTICE', 'Practice'),
    ]

    SYLLABUS_CHOICES = [
        ('MIDTERM', 'Midterm'),
        ('FINAL', 'Final'),
        ('GENERAL', 'General'),
    ]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='resources',
        help_text="Select the course this resource belongs to."
    )

    title = models.CharField(
        max_length=200,
        help_text="Example: MSMA Playlist, Midterm Slides, Final Past Question"
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        help_text="Select what kind of material this is."
    )

    exam_part = models.CharField(
        "Syllabus",
        max_length=20,
        choices=SYLLABUS_CHOICES,
        default='GENERAL',
        help_text="Choose whether this belongs to Midterm, Final, or General syllabus."
    )

    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
        blank=True,
        help_text="Only fill this if Category is Questions."
    )

    description = models.TextField(
        blank=True,
        help_text="Optional short explanation about this resource."
    )

    file = models.FileField(
        upload_to='resources/',
        blank=True,
        null=True,
        help_text="Upload file here if you want to store the file directly."
    )

    external_link = models.URLField(
        blank=True,
        help_text="Paste Google Drive, YouTube, playlist, or useful website link here."
    )

    solution_file = models.FileField(
    upload_to='resources/solutions/',
    blank=True,
    null=True,
    help_text="Optional. Upload solution/answer file only for question resources."
    )

    solution_link = models.URLField(
    blank=True,
    help_text="Optional. Paste solution/answer link only for question resources."
    )

    semester = models.CharField(
        max_length=50,
        blank=True,
        help_text="Optional. Example: Spring 2025, Summer 2026"
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        errors = {}

        if not self.file and not self.external_link:
            errors['file'] = "Please upload a file or provide an external link."
            errors['external_link'] = "Please upload a file or provide an external link."

        if self.category == 'QUESTION':
            if not self.question_type:
                errors['question_type'] = "Question type is required when category is Questions."
        else:
            if self.question_type:
                errors['question_type'] = "Question type should only be selected when category is Questions."

        if self.category != 'QUESTION' and (self.solution_file or self.solution_link):
           raise ValidationError("Solutions can only be added for question resources.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.category != 'QUESTION':
            self.question_type = ''

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.course.course_code} - {self.title}"


class ReportIssue(models.Model):
    ISSUE_TYPE_CHOICES = [
        ('BROKEN_LINK', 'Broken link'),
        ('WRONG_RESOURCE', 'Wrong course/resource'),
        ('REMOVAL_REQUEST', 'Request removal'),
        ('SUGGEST_RESOURCE', 'Suggest new resource'),
        ('OTHER', 'Other'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CHECKED', 'Checked'),
        ('RESOLVED', 'Resolved'),
    ]

    issue_type = models.CharField(
        max_length=30,
        choices=ISSUE_TYPE_CHOICES,
        help_text="Select what kind of issue this is."
    )

    course_code = models.CharField(
        max_length=30,
        blank=True,
        help_text="Example: CSE421, MAT215"
    )

    resource_title_or_link = models.CharField(
        max_length=300,
        blank=True,
        help_text="Paste the resource title or link if possible."
    )

    details = models.TextField(
        help_text="Describe the problem."
    )

    contact_email = models.EmailField(
        blank=True,
        help_text="Optional. Student can leave email if they want a reply."
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_issue_type_display()} - {self.course_code or 'No course'}"