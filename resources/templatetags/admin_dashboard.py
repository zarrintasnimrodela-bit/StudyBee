from django import template

from resources.models import ReportIssue, Resource, ResourceSubmission


register = template.Library()


@register.simple_tag
def studybee_admin_counts():
    return {
        "pending_submissions": ResourceSubmission.objects.filter(
            status="PENDING"
        ).count(),
        "open_reports": ReportIssue.objects.exclude(status="RESOLVED").count(),
        "needs_review": Resource.objects.filter(
            verification_status="NEEDS_REVIEW"
        ).count(),
        "failed_notifications": ReportIssue.objects.exclude(
            notification_error=""
        ).count(),
    }
