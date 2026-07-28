from django import forms

from .models import ReportIssue, ResourceSubmission


class ReportIssueForm(forms.ModelForm):
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
            "issue_type": forms.Select(
                attrs={"class": "report-input"}
            ),
            "course_code": forms.TextInput(
                attrs={
                    "class": "report-input",
                    "placeholder": "Example: CSE421",
                }
            ),
            "resource_title_or_link": forms.TextInput(
                attrs={
                    "class": "report-input",
                    "placeholder": (
                        "Paste resource title or link if possible"
                    ),
                }
            ),
            "details": forms.Textarea(
                attrs={
                    "class": "report-input report-textarea",
                    "placeholder": "Explain what is wrong...",
                    "rows": 5,
                }
            ),
            "contact_email": forms.EmailInput(
                attrs={
                    "class": "report-input",
                    "placeholder": (
                        "Optional — enter email for a resolution update"
                    ),
                }
            ),
        }


class ResourceSubmissionForm(forms.ModelForm):
    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

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
            "submitter_name",
            "submitter_email",
            "note_to_admin",
        )

        widgets = {
            "course": forms.Select(
                attrs={"class": "report-input"}
            ),
            "title": forms.TextInput(
                attrs={
                    "class": "report-input",
                    "placeholder": "Resource title",
                }
            ),
            "category": forms.Select(
                attrs={"class": "report-input"}
            ),
            "exam_part": forms.Select(
                attrs={"class": "report-input"}
            ),
            "question_type": forms.Select(
                attrs={"class": "report-input"}
            ),
            "semester_term": forms.Select(
                attrs={"class": "report-input"}
            ),
            "semester_year": forms.NumberInput(
                attrs={
                    "class": "report-input",
                    "placeholder": "Example: 2026",
                    "min": "2000",
                    "max": "2100",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "report-input report-textarea",
                    "rows": 4,
                    "placeholder": (
                        "Optional explanation of the resource"
                    ),
                }
            ),
            "file": forms.ClearableFileInput(
                attrs={
                    "class": "report-input",
                    "accept": (
                        ".pdf,.doc,.docx,.ppt,.pptx,"
                        ".xls,.xlsx,.zip,.png,.jpg,.jpeg"
                    ),
                }
            ),
            "external_link": forms.URLInput(
                attrs={
                    "class": "report-input",
                    "placeholder": (
                        "Google Drive, YouTube, or another URL"
                    ),
                }
            ),
            "solution_file": forms.ClearableFileInput(
                attrs={
                    "class": "report-input",
                    "accept": (
                        ".pdf,.doc,.docx,.ppt,.pptx,"
                        ".xls,.xlsx,.zip,.png,.jpg,.jpeg"
                    ),
                }
            ),
            "solution_link": forms.URLInput(
                attrs={
                    "class": "report-input",
                    "placeholder": "Optional solution URL",
                }
            ),
            "submitter_name": forms.TextInput(
                attrs={
                    "class": "report-input",
                    "placeholder": "Optional",
                }
            ),
            "submitter_email": forms.EmailInput(
                attrs={
                    "class": "report-input",
                    "placeholder": "Optional",
                }
            ),
            "note_to_admin": forms.Textarea(
                attrs={
                    "class": "report-input report-textarea",
                    "rows": 3,
                    "placeholder": (
                        "Optional source or context for the admin"
                    ),
                }
            ),
        }

    def clean_website(self):
        value = self.cleaned_data.get("website", "")

        if value:
            raise forms.ValidationError(
                "Submission could not be accepted."
            )

        return value


class BulkImportForm(forms.Form):
    csv_file = forms.FileField(
        help_text="Upload a UTF-8 CSV file.",
        widget=forms.ClearableFileInput(
            attrs={"accept": ".csv"}
        ),
    )
