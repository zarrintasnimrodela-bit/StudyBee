import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .validators import validate_resource_file


SEMESTER_TERM_CHOICES = [
    ("SPRING", "Spring"),
    ("SUMMER", "Summer"),
    ("FALL", "Fall"),
]


def student_name_from_email(email):
    """Build a readable student name from the email's local part."""
    local_part = (email or "").strip().split("@", 1)[0]
    words = [
        word
        for word in re.split(r"[._-]+", local_part)
        if word
    ]
    return " ".join(word.capitalize() for word in words)


def parse_legacy_semester(value):
    match = re.match(
        r"^\s*(spring|summer|fall)\s+(\d{4})\s*$",
        value or "",
        flags=re.IGNORECASE,
    )

    if not match:
        return "", None

    return match.group(1).upper(), int(match.group(2))


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    display_name = models.CharField(max_length=120, blank=True)
    verified_email = models.EmailField(unique=True)
    email_verified_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.verified_email = self.verified_email.strip().lower()
        self.display_name = student_name_from_email(self.verified_email)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.verified_email


class EmailVerificationCode(models.Model):
    PURPOSE_CHOICES = [
        ("SIGNUP", "Sign up"),
        ("PASSWORD_RESET", "Password reset"),
    ]

    email = models.EmailField(db_index=True)
    purpose = models.CharField(
        max_length=20,
        choices=PURPOSE_CHOICES,
        default="SIGNUP",
        db_index=True,
    )
    code_digest = models.CharField(max_length=64)
    request_ip = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(blank=True, null=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["email", "created_at"],
                name="otp_email_created_idx",
            ),
            models.Index(
                fields=["email", "purpose", "created_at"],
                name="otp_email_purpose_idx",
            ),
        ]

    @staticmethod
    def digest_for(email, code):
        normalized_email = email.strip().lower()
        return salted_hmac(
            "studybee.email-otp",
            f"{normalized_email}:{code}",
        ).hexdigest()

    @classmethod
    def issue(
        cls,
        *,
        email,
        purpose="SIGNUP",
        request_ip=None,
        lifetime_minutes=10,
    ):
        normalized_email = email.strip().lower()
        code = f"{secrets.randbelow(1_000_000):06d}"

        cls.objects.filter(
            email=normalized_email,
            purpose=purpose,
            used_at__isnull=True,
        ).update(used_at=timezone.now())

        record = cls.objects.create(
            email=normalized_email,
            purpose=purpose,
            code_digest=cls.digest_for(normalized_email, code),
            request_ip=request_ip or None,
            expires_at=(
                timezone.now() + timedelta(minutes=lifetime_minutes)
            ),
        )
        return record, code

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    @property
    def is_usable(self):
        return (
            self.used_at is None
            and not self.is_expired
            and self.attempts < 5
        )

    def matches(self, code):
        expected = self.digest_for(self.email, str(code).strip())
        return constant_time_compare(self.code_digest, expected)

    def __str__(self):
        return (
            f"{self.get_purpose_display()} OTP for {self.email} "
            f"at {self.created_at:%Y-%m-%d %H:%M}"
        )


class Course(models.Model):
    LAB_TYPE_CHOICES = [
        ("NO_LAB", "No Lab"),
        ("WEEKLY", "Weekly Lab"),
        ("BIWEEKLY", "Biweekly Lab"),
    ]

    course_code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Example: CSE421, CSE370, CSE220",
    )

    course_title = models.CharField(
        max_length=200,
        help_text="Example: Computer Networks, Database Systems",
    )

    description = models.TextField(
        blank=True,
        help_text="Short description shown on the course page.",
    )

    hard_prerequisite = models.CharField(
        max_length=250,
        blank=True,
        help_text=(
            "Example: CSE220, CSE221. "
            "Leave empty if there is no hard prerequisite."
        ),
    )

    soft_prerequisite = models.CharField(
        max_length=250,
        blank=True,
        help_text=(
            "Example: CSE370. "
            "Optional course that helps but is not mandatory."
        ),
    )

    lab_type = models.CharField(
        max_length=20,
        choices=LAB_TYPE_CHOICES,
        default="NO_LAB",
        help_text="Select lab type for this course.",
    )

    def save(self, *args, **kwargs):
        self.course_code = self.course_code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.course_code} - {self.course_title}"


class Resource(models.Model):
    CATEGORY_CHOICES = [
        ("SLIDE", "Slides"),
        ("NOTE", "Notes"),
        ("QUESTION", "Questions"),
        ("LAB", "Lab Files"),
        ("VIDEO", "Videos"),
        ("BOOK", "Books"),
        ("LINK", "Useful Links"),
        ("OTHER", "Other"),
    ]

    QUESTION_TYPE_CHOICES = [
        ("PAST_EXAM", "Past Exam"),
        ("ASSIGNMENT", "Assignment"),
        ("QUIZ", "Quiz"),
        ("PRACTICE", "Practice"),
    ]

    SYLLABUS_CHOICES = [
        ("MIDTERM", "Midterm"),
        ("FINAL", "Final"),
        ("GENERAL", "General"),
    ]

    VERIFICATION_CHOICES = [
        ("UNVERIFIED", "Unverified"),
        ("VERIFIED", "Verified"),
        ("NEEDS_REVIEW", "Needs review"),
        ("BROKEN", "Broken"),
    ]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="resources",
        help_text="Select the course this resource belongs to.",
    )

    title = models.CharField(
        max_length=200,
        help_text=(
            "Example: MSMA Playlist, Midterm Slides, "
            "Final Past Question"
        ),
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        help_text="Select what kind of material this is.",
    )

    exam_part = models.CharField(
        "Syllabus",
        max_length=20,
        choices=SYLLABUS_CHOICES,
        default="GENERAL",
        help_text=(
            "Choose whether this belongs to Midterm, "
            "Final, or General syllabus."
        ),
    )

    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
        blank=True,
        help_text="Only fill this if Category is Questions.",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional short explanation about this resource.",
    )

    file = models.FileField(
        upload_to="resources/",
        blank=True,
        null=True,
        validators=[validate_resource_file],
        help_text=(
            "Upload file here if you want to store "
            "the file directly."
        ),
    )

    external_link = models.URLField(
        blank=True,
        help_text=(
            "Paste Google Drive, YouTube, playlist, "
            "or useful website link here."
        ),
    )

    solution_file = models.FileField(
        upload_to="resources/solutions/",
        blank=True,
        null=True,
        validators=[validate_resource_file],
        help_text=(
            "Optional. Upload solution/answer file only "
            "for question resources."
        ),
    )

    solution_link = models.URLField(
        blank=True,
        help_text=(
            "Optional. Paste solution/answer link "
            "only for question resources."
        ),
    )

    semester = models.CharField(
        max_length=50,
        blank=True,
        help_text=(
            "Optional. Example: Spring 2025, Summer 2026"
        ),
    )

    semester_term = models.CharField(
        max_length=10,
        choices=SEMESTER_TERM_CHOICES,
        blank=True,
    )

    semester_year = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[
            MinValueValidator(2000),
            MaxValueValidator(2100),
        ],
    )

    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_CHOICES,
        default="UNVERIFIED",
        db_index=True,
    )

    verified_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="verified_resources",
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["semester_term", "semester_year"],
                name="resource_semester_idx",
            ),
        ]

    @property
    def semester_display(self):
        if self.semester_term and self.semester_year:
            return (
                f"{self.get_semester_term_display()} "
                f"{self.semester_year}"
            )

        return self.semester

    def clean(self):
        errors = {}

        if not self.file and not self.external_link:
            errors["file"] = (
                "Please upload a file or provide an external link."
            )
            errors["external_link"] = (
                "Please upload a file or provide an external link."
            )

        if self.category == "QUESTION":
            if not self.question_type:
                errors["question_type"] = (
                    "Question type is required when category is Questions."
                )
        elif self.question_type:
            errors["question_type"] = (
                "Question type should only be selected "
                "when category is Questions."
            )

        if self.category != "QUESTION" and (
            self.solution_file or self.solution_link
        ):
            errors["solution_file"] = (
                "Solutions can only be added for question resources."
            )
            errors["solution_link"] = (
                "Solutions can only be added for question resources."
            )

        if bool(self.semester_term) != bool(self.semester_year):
            errors["semester_term"] = (
                "Choose both semester term and semester year."
            )
            errors["semester_year"] = (
                "Choose both semester term and semester year."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.category != "QUESTION":
            self.question_type = ""

        if (
            not self.semester_term
            and not self.semester_year
            and self.semester
        ):
            term, year = parse_legacy_semester(self.semester)
            self.semester_term = term
            self.semester_year = year

        if self.semester_term and self.semester_year:
            self.semester = (
                f"{self.get_semester_term_display()} "
                f"{self.semester_year}"
            )

        if self.verification_status == "VERIFIED":
            if not self.verified_at:
                self.verified_at = timezone.now()
        else:
            self.verified_at = None

            if self.verification_status != "VERIFIED":
                self.verified_by = None

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.course.course_code} - {self.title}"


class ResourceSubmission(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="resource_submissions",
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="resource_submissions",
    )

    title = models.CharField(max_length=200)

    category = models.CharField(
        max_length=20,
        choices=Resource.CATEGORY_CHOICES,
    )

    exam_part = models.CharField(
        "Syllabus",
        max_length=20,
        choices=Resource.SYLLABUS_CHOICES,
        default="GENERAL",
    )

    question_type = models.CharField(
        max_length=20,
        choices=Resource.QUESTION_TYPE_CHOICES,
        blank=True,
    )

    description = models.TextField(blank=True)

    file = models.FileField(
        upload_to="submissions/resources/",
        blank=True,
        null=True,
        validators=[validate_resource_file],
    )

    external_link = models.URLField(blank=True)

    solution_file = models.FileField(
        upload_to="submissions/solutions/",
        blank=True,
        null=True,
        validators=[validate_resource_file],
    )

    solution_link = models.URLField(blank=True)

    semester_term = models.CharField(
        max_length=10,
        choices=SEMESTER_TERM_CHOICES,
        blank=True,
    )

    semester_year = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[
            MinValueValidator(2000),
            MaxValueValidator(2100),
        ],
    )

    submitter_name = models.CharField(
        max_length=120,
        blank=True,
    )

    submitter_email = models.EmailField(blank=True)

    note_to_admin = models.TextField(blank=True)

    published_resource = models.OneToOneField(
        Resource,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="source_submission",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True,
    )

    review_notes = models.TextField(blank=True)

    reviewed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_resource_submissions",
    )

    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]

    @property
    def reference_code(self):
        return f"SB-S{self.pk:06d}" if self.pk else "Pending"

    @property
    def semester_display(self):
        if self.semester_term and self.semester_year:
            label = dict(SEMESTER_TERM_CHOICES).get(
                self.semester_term,
                self.semester_term.title(),
            )
            return f"{label} {self.semester_year}"

        return ""

    def clean(self):
        errors = {}

        if not self.file and not self.external_link:
            errors["file"] = (
                "Please upload a file or provide an external link."
            )
            errors["external_link"] = (
                "Please upload a file or provide an external link."
            )

        if self.category == "QUESTION":
            if not self.question_type:
                errors["question_type"] = (
                    "Question type is required for question resources."
                )
        elif self.question_type:
            errors["question_type"] = (
                "Question type is only allowed for Questions."
            )

        if self.category != "QUESTION" and (
            self.solution_file or self.solution_link
        ):
            errors["solution_file"] = (
                "Solutions are only allowed for question resources."
            )
            errors["solution_link"] = (
                "Solutions are only allowed for question resources."
            )

        if bool(self.semester_term) != bool(self.semester_year):
            errors["semester_term"] = (
                "Choose both semester term and semester year."
            )
            errors["semester_year"] = (
                "Choose both semester term and semester year."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.category != "QUESTION":
            self.question_type = ""

        self.full_clean()
        super().save(*args, **kwargs)

    def _matching_published_resource(self):
        candidates = Resource.objects.filter(
            course=self.course,
            title__iexact=self.title,
        )

        if self.external_link:
            candidates = candidates.filter(
                external_link=self.external_link
            )
        elif self.file:
            candidates = candidates.filter(
                file=self.file.name
            )
        else:
            return None

        return candidates.order_by("id").first()

    @transaction.atomic
    def approve(self, user=None):
        previous_status = self.status

        if self.published_resource_id:
            resource = self.published_resource
        else:
            resource = self._matching_published_resource()

        if resource is None:
            resource = Resource(
                course=self.course,
                title=self.title,
                category=self.category,
                exam_part=self.exam_part,
                question_type=self.question_type,
                description=self.description,
                file=self.file,
                external_link=self.external_link,
                solution_file=self.solution_file,
                solution_link=self.solution_link,
                semester_term=self.semester_term,
                semester_year=self.semester_year,
                verification_status="UNVERIFIED",
            )
            resource.save()
        elif resource.verification_status in {
            "NEEDS_REVIEW",
            "BROKEN",
        }:
            resource.verification_status = "UNVERIFIED"
            resource.verified_by = None
            resource.verified_at = None
            resource.save(
                update_fields=[
                    "verification_status",
                    "verified_by",
                    "verified_at",
                    "updated_at",
                ]
            )

        self.status = "APPROVED"
        self.published_resource = resource
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "published_resource",
                "reviewed_by",
                "reviewed_at",
            ]
        )

        if previous_status != "APPROVED":
            submission_id = self.pk
            transaction.on_commit(
                lambda: self._notify_review_after_commit(submission_id)
            )

        return resource

    def reject(self, user=None):
        previous_status = self.status
        self.status = "REJECTED"
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
            ]
        )

        if previous_status != "REJECTED":
            submission_id = self.pk
            transaction.on_commit(
                lambda: self._notify_review_after_commit(submission_id)
            )

    @staticmethod
    def _notify_review_after_commit(submission_id):
        from .notifications import send_submission_review_email

        send_submission_review_email(submission_id)

    def __str__(self):
        return (
            f"{self.course.course_code} - {self.title} "
            f"({self.get_status_display()})"
        )


class ReportIssue(models.Model):
    ISSUE_TYPE_CHOICES = [
        ("BROKEN_LINK", "Broken link"),
        ("WRONG_RESOURCE", "Wrong course/resource"),
        ("REMOVAL_REQUEST", "Request removal"),
        ("SUGGEST_RESOURCE", "Suggest new resource"),
        ("OTHER", "Other"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("CHECKED", "Checked"),
        ("RESOLVED", "Resolved"),
    ]

    RESOLUTION_CHOICES = [
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
    ]

    resource = models.ForeignKey(
        Resource,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="issue_reports",
    )

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="issue_reports",
    )

    issue_type = models.CharField(
        max_length=30,
        choices=ISSUE_TYPE_CHOICES,
        help_text="Select what kind of issue this is.",
    )

    course_code = models.CharField(
        max_length=30,
        blank=True,
        help_text="Example: CSE421, MAT215",
    )

    resource_title_or_link = models.CharField(
        max_length=300,
        blank=True,
        help_text="Paste the resource title or link if possible.",
    )

    details = models.TextField(
        help_text="Describe the problem.",
    )

    contact_email = models.EmailField(
        blank=True,
        help_text=(
            "Optional. Student can leave email "
            "if they want a reply."
        ),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True,
    )

    resolution = models.CharField(
        max_length=20,
        choices=RESOLUTION_CHOICES,
        blank=True,
    )

    admin_response = models.TextField(
        blank=True,
        help_text=(
            "Optional message included in the reporter email. "
            "A default message is used when this is blank."
        ),
    )

    resolved_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="resolved_resource_reports",
    )

    notification_sent_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    notification_error = models.TextField(
        blank=True,
    )

    submitted_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.resource:
            if not self.course_code:
                self.course_code = self.resource.course.course_code

            if not self.resource_title_or_link:
                self.resource_title_or_link = self.resource.title

        super().save(*args, **kwargs)

    @property
    def reference_code(self):
        return f"SB-R{self.pk:06d}" if self.pk else "Pending"

    @property
    def resource_label(self):
        if self.resource:
            return (
                f"{self.resource.course.course_code} — "
                f"{self.resource.title}"
            )

        return self.resource_title_or_link or self.course_code or "Resource"

    def default_admin_response(self, resolution=None):
        outcome = resolution or self.resolution

        messages = {
            "REPUBLISHED": (
                "We reviewed the report, fixed the issue where possible, "
                "and made the resource publicly available again."
            ),
            "REMOVED": (
                "We reviewed the report and kept the resource removed "
                "from the public StudyBee site."
            ),
            "DISMISSED": (
                "We reviewed the report and did not find a reason to keep "
                "the resource hidden, so it is publicly available again."
            ),
        }

        return messages.get(
            outcome,
            "We reviewed your report and completed the required action.",
        )

    @transaction.atomic
    def resolve(self, resolution, user=None, admin_response=""):
        valid_resolutions = {
            choice[0] for choice in self.RESOLUTION_CHOICES
        }

        if resolution not in valid_resolutions:
            raise ValueError("Unknown report resolution.")

        if self.resource_id:
            resource = Resource.objects.select_for_update().filter(
                pk=self.resource_id
            ).first()

            if resource:
                if resolution in {"REPUBLISHED", "DISMISSED"}:
                    resource.verification_status = "UNVERIFIED"
                elif resolution == "REMOVED":
                    resource.verification_status = "BROKEN"

                resource.verified_by = None
                resource.verified_at = None
                resource.save(
                    update_fields=[
                        "verification_status",
                        "verified_by",
                        "verified_at",
                        "updated_at",
                    ]
                )

        self.status = "RESOLVED"
        self.resolution = resolution
        self.admin_response = (
            admin_response.strip()
            or self.admin_response.strip()
            or self.default_admin_response(resolution)
        )
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.notification_sent_at = None
        self.notification_error = ""
        self.save(
            update_fields=[
                "status",
                "resolution",
                "admin_response",
                "resolved_by",
                "resolved_at",
                "notification_sent_at",
                "notification_error",
            ]
        )

        report_id = self.pk

        transaction.on_commit(
            lambda: self._notify_after_commit(report_id)
        )

    @staticmethod
    def _notify_after_commit(report_id):
        from .notifications import send_report_resolution_email

        send_report_resolution_email(report_id)

    def __str__(self):
        return (
            f"{self.get_issue_type_display()} - "
            f"{self.course_code or 'No course'}"
        )
