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
