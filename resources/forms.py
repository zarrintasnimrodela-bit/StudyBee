from django import forms
from .models import ReportIssue


class ReportIssueForm(forms.ModelForm):
    class Meta:
        model = ReportIssue
        fields = (
            'issue_type',
            'course_code',
            'resource_title_or_link',
            'details',
            'contact_email',
        )

        widgets = {
            'issue_type': forms.Select(attrs={
                'class': 'report-input',
            }),
            'course_code': forms.TextInput(attrs={
                'class': 'report-input',
                'placeholder': 'Example: CSE421',
            }),
            'resource_title_or_link': forms.TextInput(attrs={
                'class': 'report-input',
                'placeholder': 'Paste resource title or link if possible',
            }),
            'details': forms.Textarea(attrs={
                'class': 'report-input report-textarea',
                'placeholder': 'Explain what is wrong...',
                'rows': 5,
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'report-input',
                'placeholder': 'Optional',
            }),
        }