import json
import logging
from urllib import error, request

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import ReportIssue


logger = logging.getLogger(__name__)


RESOLUTION_LABELS = {
    "REPUBLISHED": "Issue fixed and resource republished",
    "REMOVED": "Resource removed from the public site",
    "DISMISSED": "Report dismissed and resource republished",
}


def build_report_resolution_email(report):
    outcome = RESOLUTION_LABELS.get(
        report.resolution,
        "Report reviewed",
    )

    subject = (
        "StudyBee report update: "
        f"{report.resource_label}"
    )

    lines = [
        "Hello,",
        "",
        "An admin has reviewed the issue you reported on StudyBee.",
        "",
        f"Resource: {report.resource_label}",
        f"Issue: {report.get_issue_type_display()}",
        f"Outcome: {outcome}",
        "",
        report.admin_response or report.default_admin_response(),
        "",
        "Thank you for helping keep StudyBee useful and accurate.",
        "",
        "— StudyBee",
    ]

    return subject, "\n".join(lines)


def send_with_brevo(*, subject, body, recipient):
    api_key = getattr(settings, "BREVO_API_KEY", "").strip()
    sender_email = getattr(
        settings,
        "BREVO_SENDER_EMAIL",
        "",
    ).strip()
    sender_name = (
        getattr(settings, "BREVO_SENDER_NAME", "StudyBee").strip()
        or "StudyBee"
    )

    if not api_key or not sender_email:
        return False

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "to": [{"email": recipient}],
        "subject": subject,
        "textContent": body,
    }

    email_request = request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(
            email_request,
            timeout=20,
        ) as response:
            status = getattr(response, "status", 200)

            if not 200 <= status < 300:
                raise RuntimeError(
                    f"Brevo returned HTTP {status}."
                )
    except error.HTTPError as exc:
        response_body = exc.read().decode(
            "utf-8",
            errors="replace",
        )[:1000]
        raise RuntimeError(
            f"Brevo returned HTTP {exc.code}: {response_body}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(
            f"Could not reach Brevo: {exc.reason}"
        ) from exc

    return True


def send_studybee_email(*, subject, body, recipient):
    if send_with_brevo(
        subject=subject,
        body=body,
        recipient=recipient,
    ):
        return True

    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        fail_silently=False,
    )
    return True


def send_report_resolution_email(report_id):
    report = ReportIssue.objects.select_related(
        "resource",
        "resource__course",
    ).filter(pk=report_id).first()

    if not report or not report.contact_email:
        return False

    if report.status != "RESOLVED":
        return False

    subject, body = build_report_resolution_email(report)

    try:
        send_studybee_email(
            subject=subject,
            body=body,
            recipient=report.contact_email,
        )
    except Exception as exc:
        error_message = str(exc)[:1000]
        ReportIssue.objects.filter(pk=report.pk).update(
            notification_error=error_message,
            notification_sent_at=None,
        )
        logger.exception(
            "Could not send StudyBee report resolution email for report %s",
            report.pk,
        )
        return False

    ReportIssue.objects.filter(pk=report.pk).update(
        notification_sent_at=timezone.now(),
        notification_error="",
    )
    return True


def send_account_code_email(*, email, code, lifetime_minutes, purpose):
    labels = {
        "SIGNUP": (
            "Your StudyBee sign-up code",
            "sign-up verification code",
        ),
        "PASSWORD_RESET": (
            "Your StudyBee password reset code",
            "password reset code",
        ),
    }
    subject, code_label = labels.get(
        purpose,
        ("Your StudyBee verification code", "verification code"),
    )
    body = "\n".join(
        [
            "Hello,",
            "",
            f"Your StudyBee {code_label} is: {code}",
            "",
            f"This code expires in {lifetime_minutes} minutes and can be used once.",
            "If you did not request this code, you can ignore this email.",
            "",
            "StudyBee will never ask for your BRACU Google password.",
            "",
            "— StudyBee",
        ]
    )
    return send_studybee_email(
        subject=subject,
        body=body,
        recipient=email,
    )


def send_login_code_email(*, email, code, lifetime_minutes):
    """Backward-compatible wrapper for older callers."""
    return send_account_code_email(
        email=email,
        code=code,
        lifetime_minutes=lifetime_minutes,
        purpose="SIGNUP",
    )


def _send_workflow_email(*, subject, body, recipient, context):
    """Send a non-critical workflow email without breaking the user action."""
    try:
        return send_studybee_email(
            subject=subject,
            body=body,
            recipient=recipient,
        )
    except Exception:
        logger.exception("Could not send StudyBee %s email to %s", context, recipient)
        return False


def send_submission_received_email(submission_id):
    from .models import ResourceSubmission

    submission = ResourceSubmission.objects.select_related("course").filter(
        pk=submission_id
    ).first()
    if not submission or not submission.submitter_email:
        return False

    subject = f"StudyBee received {submission.reference_code}"
    body = "\n".join(
        [
            "Hello,",
            "",
            "Your resource submission has been received and is waiting for review.",
            "",
            f"Reference: {submission.reference_code}",
            f"Course: {submission.course.course_code}",
            f"Resource: {submission.title}",
            f"Status: {submission.get_status_display()}",
            "",
            "You can log in to StudyBee to view its current status.",
            "",
            "— StudyBee",
        ]
    )
    return _send_workflow_email(
        subject=subject,
        body=body,
        recipient=submission.submitter_email,
        context="submission receipt",
    )


def send_submission_review_email(submission_id):
    from .models import ResourceSubmission

    submission = ResourceSubmission.objects.select_related("course").filter(
        pk=submission_id
    ).first()
    if (
        not submission
        or not submission.submitter_email
        or submission.status not in {"APPROVED", "REJECTED"}
    ):
        return False

    if submission.status == "APPROVED":
        outcome = "approved and published"
        next_step = (
            "The resource is now available on the public StudyBee course page."
        )
    else:
        outcome = "not approved"
        next_step = (
            "You may submit a corrected version after reviewing the note below."
        )

    lines = [
        "Hello,",
        "",
        f"Your StudyBee submission has been {outcome}.",
        "",
        f"Reference: {submission.reference_code}",
        f"Course: {submission.course.course_code}",
        f"Resource: {submission.title}",
        f"Status: {submission.get_status_display()}",
        "",
        next_step,
    ]
    if submission.review_notes:
        lines.extend(["", "Reviewer note:", submission.review_notes])
    lines.extend(["", "— StudyBee"])

    return _send_workflow_email(
        subject=f"StudyBee submission update: {submission.reference_code}",
        body="\n".join(lines),
        recipient=submission.submitter_email,
        context="submission review",
    )


def send_report_received_email(report_id):
    report = ReportIssue.objects.select_related(
        "resource",
        "resource__course",
    ).filter(pk=report_id).first()

    if not report or not report.contact_email:
        return False

    body = "\n".join(
        [
            "Hello,",
            "",
            "StudyBee received your report and placed it in the moderation queue.",
            "",
            f"Reference: {report.reference_code}",
            f"Resource: {report.resource_label}",
            f"Issue: {report.get_issue_type_display()}",
            f"Status: {report.get_status_display()}",
            "",
            "You will receive another email after an admin resolves the report.",
            "",
            "— StudyBee",
        ]
    )
    return _send_workflow_email(
        subject=f"StudyBee received {report.reference_code}",
        body=body,
        recipient=report.contact_email,
        context="report receipt",
    )
