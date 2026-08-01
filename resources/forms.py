from django import forms
from django.conf import settings
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

from .models import ReportIssue, ResourceSubmission


INPUT_CLASS = "report-input"


def normalize_student_email(value):
    email = (value or "").strip().lower()
    domain = getattr(
        settings,
        "BRACU_ALLOWED_EMAIL_DOMAIN",
        "g.bracu.ac.bd",
    ).strip().lower()

    if not email or "@" not in email:
        raise forms.ValidationError("Enter a valid BRACU email address.")

    if email.rsplit("@", 1)[1] != domain:
        raise forms.ValidationError(
            f"Use your @{domain} BRACU email address."
        )

    return email


class StudentLoginForm(forms.Form):
    email = forms.EmailField(
        label="BRACU email",
        widget=forms.EmailInput(
            attrs={
                "class": INPUT_CLASS,
                "autocomplete": "email",
                "placeholder": "student@g.bracu.ac.bd",
                "inputmode": "email",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": INPUT_CLASS,
                "autocomplete": "current-password",
                "placeholder": "Your StudyBee password",
            }
        ),
    )
    remember_me = forms.BooleanField(
        label="Keep me logged in",
        required=False,
    )

    def clean_email(self):
        return normalize_student_email(self.cleaned_data["email"])


class StudentEmailForm(forms.Form):
    email = forms.EmailField(
        label="BRACU email",
        widget=forms.EmailInput(
            attrs={
                "class": INPUT_CLASS,
                "autocomplete": "email",
                "placeholder": "student@g.bracu.ac.bd",
                "inputmode": "email",
            }
        ),
    )

    def clean_email(self):
        return normalize_student_email(self.cleaned_data["email"])


class StudentCodePasswordForm(forms.Form):
    code = forms.CharField(
        label="Six-digit code",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "pattern": "[0-9]{6}",
                "placeholder": "000000",
            }
        ),
    )
    password1 = forms.CharField(
        label="Create password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": INPUT_CLASS,
                "autocomplete": "new-password",
                "placeholder": "At least 8 characters",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": INPUT_CLASS,
                "autocomplete": "new-password",
                "placeholder": "Repeat your password",
            }
        ),
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError("Enter the six-digit code.")
        return code

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The passwords do not match.")
            return cleaned

        if password1:
            minimum = getattr(settings, "STUDENT_PASSWORD_MIN_LENGTH", 8)
            if len(password1) < minimum:
                self.add_error(
                    "password1",
                    f"Use at least {minimum} characters.",
                )
            else:
                try:
                    password_validation.validate_password(password1)
                except ValidationError as exc:
                    self.add_error("password1", exc)

        return cleaned


# Compatibility aliases for older imports and migrations/tests.
StudentEmailLoginForm = StudentEmailForm
StudentOTPForm = StudentCodePasswordForm


class ReportIssueForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user and user.is_authenticated and user.email:
            self.fields["contact_email"].initial = user.email
            self.fields["contact_email"].widget.attrs.update(
                {
                    "readonly": "readonly",
                    "aria-readonly": "true",
                }
            )
            self.fields["contact_email"].help_text = (
                "Updates will be sent to your verified BRACU email."
            )

    class Meta:
        model = ReportIssue
        fields = (
            "resource",
            "issue_type",
            "course_code",
            "resource_title_or_link",
            "details",
            "contact_email",
        )
        widgets = {
            "resource": forms.HiddenInput(),
            "issue_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "course_code": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "Example: CSE421",
                    "autocomplete": "off",
                }
            ),
            "resource_title_or_link": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "Resource title or link",
                }
            ),
            "details": forms.Textarea(
                attrs={
                    "class": f"{INPUT_CLASS} report-textarea",
                    "placeholder": "Explain what is wrong and what you expected...",
                    "rows": 5,
                }
            ),
            "contact_email": forms.EmailInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "Optional — email for a resolution update",
                    "autocomplete": "email",
                }
            ),
        }

    def clean_contact_email(self):
        if self.user and self.user.is_authenticated and self.user.email:
            return self.user.email.strip().lower()
        return (self.cleaned_data.get("contact_email") or "").strip().lower()

    def clean_website(self):
        value = self.cleaned_data.get("website", "")
        if value:
            raise forms.ValidationError("Report could not be accepted.")
        return value

class ResourceSubmissionForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = ResourceSubmission
        fields = (
            "course",
            "title",
            "category",
            "exam_part",
            "question_type",
            "semester_term",
            "semester_year",
            "description",
            "file",
            "external_link",
            "solution_file",
            "solution_link",
            "note_to_admin",
        )
        widgets = {
            "course": forms.Select(attrs={"class": INPUT_CLASS}),
            "title": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "Example: Midterm lecture slides",
                    "autocomplete": "off",
                }
            ),
            "category": forms.Select(attrs={"class": INPUT_CLASS}),
            "exam_part": forms.Select(attrs={"class": INPUT_CLASS}),
            "question_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "semester_term": forms.Select(attrs={"class": INPUT_CLASS}),
            "semester_year": forms.NumberInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "2026",
                    "min": "2000",
                    "max": "2100",
                    "inputmode": "numeric",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": f"{INPUT_CLASS} report-textarea",
                    "rows": 4,
                    "placeholder": "What does this resource cover?",
                }
            ),
            "file": forms.ClearableFileInput(
                attrs={
                    "class": INPUT_CLASS,
                    "accept": (
                        ".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,"
                        ".zip,.png,.jpg,.jpeg"
                    ),
                }
            ),
            "external_link": forms.URLInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "Google Drive, YouTube, or another URL",
                    "inputmode": "url",
                }
            ),
            "solution_file": forms.ClearableFileInput(
                attrs={
                    "class": INPUT_CLASS,
                    "accept": (
                        ".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,"
                        ".zip,.png,.jpg,.jpeg"
                    ),
                }
            ),
            "solution_link": forms.URLInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "Optional solution URL",
                    "inputmode": "url",
                }
            ),
            "note_to_admin": forms.Textarea(
                attrs={
                    "class": f"{INPUT_CLASS} report-textarea",
                    "rows": 3,
                    "placeholder": "Optional source, context, or note for the reviewer",
                }
            ),
        }

    def clean_website(self):
        value = self.cleaned_data.get("website", "")
        if value:
            raise forms.ValidationError("Submission could not be accepted.")
        return value


class BulkImportForm(forms.Form):
    csv_file = forms.FileField(
        help_text="Upload a UTF-8 CSV file.",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv"}),
    )
