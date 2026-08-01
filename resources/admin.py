from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .forms import BulkImportForm
from .importers import BulkImportError, import_resources_from_csv
from .notifications import send_report_resolution_email
from .models import (
    Course,
    EmailVerificationCode,
    ReportIssue,
    Resource,
    ResourceSubmission,
    StudentProfile,
)


def _status_badge(value, label=None):
    css_value = (value or "unknown").lower()
    return format_html(
        '<span class="sb-status sb-status-{}">{}</span>',
        css_value,
        label or str(value).replace("_", " ").title(),
    )




@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "course_code",
        "course_title",
        "hard_prerequisite",
        "soft_prerequisite",
        "lab_type",
        "resource_count",
    )

    search_fields = (
        "course_code",
        "course_title",
        "hard_prerequisite",
        "soft_prerequisite",
    )

    list_filter = ("lab_type",)
    ordering = ("course_code",)

    fieldsets = (
        (
            "Course Information",
            {
                "fields": (
                    "course_code",
                    "course_title",
                    "description",
                    "hard_prerequisite",
                    "soft_prerequisite",
                    "lab_type",
                )
            },
        ),
    )

    @admin.display(description="Resources")
    def resource_count(self, obj):
        return obj.resources.count()


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    change_list_template = (
        "admin/resources/resource/change_list.html"
    )

    list_display = (
        "title",
        "course",
        "category",
        "exam_part",
        "semester_label",
        "verification_badge",
        "public_page",
        "has_solution",
        "has_file",
        "has_link",
        "updated_at",
    )

    list_filter = (
        "course",
        "category",
        "exam_part",
        "question_type",
        "semester_term",
        "semester_year",
        "verification_status",
    )

    search_fields = (
        "title",
        "course__course_code",
        "course__course_title",
        "description",
        "semester",
    )

    ordering = (
        "course__course_code",
        "category",
        "title",
    )
    list_per_page = 25

    readonly_fields = (
        "uploaded_at",
        "updated_at",
        "verified_at",
        "admin_help_text",
    )

    actions = (
        "mark_verified",
        "mark_needs_review",
        "mark_broken",
        "mark_unverified",
    )

    fieldsets = (
        (
            "1. Basic Resource Information",
            {
                "fields": (
                    "course",
                    "title",
                    "category",
                    "exam_part",
                    "semester_term",
                    "semester_year",
                )
            },
        ),
        (
            "2. Question Settings",
            {
                "fields": (
                    "question_type",
                    "admin_help_text",
                ),
                "description": (
                    "Only use this section if Category is Questions."
                ),
            },
        ),
        (
            "3. Main Resource",
            {
                "fields": (
                    "file",
                    "external_link",
                )
            },
        ),
        (
            "4. Solution / Answer",
            {
                "fields": (
                    "solution_file",
                    "solution_link",
                ),
                "description": (
                    "Optional. Only use this for question resources."
                ),
            },
        ),
        (
            "5. Verification",
            {
                "fields": (
                    "verification_status",
                    "verified_by",
                    "verified_at",
                )
            },
        ),
        (
            "6. Optional Description",
            {
                "fields": (
                    "description",
                    "uploaded_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_urls(self):
        custom_urls = [
            path(
                "bulk-import/",
                self.admin_site.admin_view(
                    self.bulk_import_view
                ),
                name="resources_resource_bulk_import",
            ),
        ]

        return custom_urls + super().get_urls()

    def bulk_import_view(self, request):
        if request.method == "POST":
            form = BulkImportForm(
                request.POST,
                request.FILES,
            )

            if form.is_valid():
                try:
                    result = import_resources_from_csv(
                        form.cleaned_data["csv_file"],
                        user=request.user,
                    )
                except BulkImportError as exc:
                    self.message_user(
                        request,
                        str(exc),
                        level=messages.ERROR,
                    )
                else:
                    self.message_user(
                        request,
                        (
                            f"Imported {result['processed_rows']} rows: "
                            f"{result['created_resources']} resources "
                            "created, "
                            f"{result['updated_resources']} updated, "
                            f"{result['created_courses']} courses created."
                        ),
                        level=messages.SUCCESS,
                    )
                    return redirect(
                        reverse(
                            "admin:resources_resource_changelist"
                        )
                    )
        else:
            form = BulkImportForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Bulk import resources",
            "form": form,
            "opts": self.model._meta,
        }

        return render(
            request,
            "admin/resources/resource/bulk_import.html",
            context,
        )

    @admin.display(description="Status", ordering="verification_status")
    def verification_badge(self, obj):
        return _status_badge(
            obj.verification_status,
            obj.get_verification_status_display(),
        )

    @admin.display(description="Public page")
    def public_page(self, obj):
        url = reverse(
            "course_detail",
            kwargs={"course_code": obj.course.course_code.lower()},
        )
        return format_html(
            '<a href="{}?focus={}" target="_blank" rel="noopener">Preview ↗</a>',
            url,
            obj.pk,
        )

    @admin.display(description="Semester")
    def semester_label(self, obj):
        return obj.semester_display or "—"

    @admin.display(description="Important Note")
    def admin_help_text(self, obj):
        return (
            "Question Type and solution fields are only for "
            "question resources."
        )

    @admin.display(boolean=True, description="File?")
    def has_file(self, obj):
        return bool(obj.file)

    @admin.display(boolean=True, description="Link?")
    def has_link(self, obj):
        return bool(obj.external_link)

    @admin.display(boolean=True, description="Solution")
    def has_solution(self, obj):
        return bool(
            obj.solution_file or obj.solution_link
        )

    @admin.action(description="Mark selected resources verified")
    def mark_verified(self, request, queryset):
        updated = queryset.update(
            verification_status="VERIFIED",
            verified_by=request.user,
            verified_at=timezone.now(),
        )
        self.message_user(
            request,
            f"{updated} resource(s) marked verified.",
        )

    @admin.action(description="Mark selected resources needs review")
    def mark_needs_review(self, request, queryset):
        updated = queryset.update(
            verification_status="NEEDS_REVIEW",
            verified_by=None,
            verified_at=None,
        )
        self.message_user(
            request,
            f"{updated} resource(s) marked needs review.",
        )

    @admin.action(description="Mark selected resources broken")
    def mark_broken(self, request, queryset):
        updated = queryset.update(
            verification_status="BROKEN",
            verified_by=None,
            verified_at=None,
        )
        self.message_user(
            request,
            f"{updated} resource(s) marked broken.",
        )

    @admin.action(description="Mark selected resources unverified")
    def mark_unverified(self, request, queryset):
        updated = queryset.update(
            verification_status="UNVERIFIED",
            verified_by=None,
            verified_at=None,
        )
        self.message_user(
            request,
            f"{updated} resource(s) marked unverified.",
        )


@admin.register(ResourceSubmission)
class ResourceSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "reference_code_display",
        "title",
        "course",
        "category",
        "semester_label",
        "status_badge",
        "published_resource_link",
        "submitter_email",
        "submitted_at",
    )

    list_filter = (
        "status",
        "category",
        "semester_term",
        "semester_year",
        "submitted_at",
    )

    search_fields = (
        "title",
        "course__course_code",
        "submitter_name",
        "submitter_email",
        "note_to_admin",
    )

    readonly_fields = (
        "submitted_at",
        "reviewed_at",
        "reviewed_by",
        "status",
        "published_resource",
        "submitted_by",
    )

    actions = (
        "approve_selected",
        "reject_selected",
    )

    fieldsets = (
        (
            "Submitted Resource",
            {
                "fields": (
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
                )
            },
        ),
        (
            "Submitter",
            {
                "fields": (
                    "submitted_by",
                    "submitter_name",
                    "submitter_email",
                    "note_to_admin",
                    "submitted_at",
                )
            },
        ),
        (
            "Review",
            {
                "fields": (
                    "status",
                    "published_resource",
                    "review_notes",
                    "reviewed_by",
                    "reviewed_at",
                )
            },
        ),
    )

    @admin.display(description="Reference")
    def reference_code_display(self, obj):
        return obj.reference_code

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return _status_badge(obj.status, obj.get_status_display())

    @admin.display(description="Semester")
    def semester_label(self, obj):
        return obj.semester_display or "—"

    @admin.display(description="Published resource")
    def published_resource_link(self, obj):
        if not obj.published_resource_id:
            return "—"

        url = reverse(
            "admin:resources_resource_change",
            args=[obj.published_resource_id],
        )
        return format_html(
            '<a href="{}">Open resource</a>',
            url,
        )

    @admin.action(description="Approve and publish selected submissions")
    def approve_selected(self, request, queryset):
        published = 0
        skipped = 0

        for submission in queryset:
            if submission.status == "REJECTED":
                skipped += 1
                continue

            submission.approve(user=request.user)
            published += 1

        self.message_user(
            request,
            (
                f"{published} submission(s) published or repaired. "
                f"{skipped} rejected submission(s) skipped."
            ),
        )

    @admin.action(description="Reject selected submissions")
    def reject_selected(self, request, queryset):
        rejected = 0
        skipped = 0

        for submission in queryset:
            if submission.status != "PENDING":
                skipped += 1
                continue

            submission.reject(user=request.user)
            rejected += 1

        self.message_user(
            request,
            (
                f"{rejected} submission(s) rejected. "
                f"{skipped} already reviewed."
            ),
        )


@admin.register(ReportIssue)
class ReportIssueAdmin(admin.ModelAdmin):
    list_display = (
        "reference_code_display",
        "issue_type",
        "linked_resource",
        "course_code",
        "status_badge",
        "resolution",
        "notification_status",
        "submitted_at",
        "contact_email",
    )

    list_filter = (
        "issue_type",
        "status",
        "resolution",
        "submitted_at",
    )

    search_fields = (
        "course_code",
        "resource__title",
        "resource_title_or_link",
        "details",
        "contact_email",
        "admin_response",
    )

    readonly_fields = (
        "resource",
        "issue_type",
        "course_code",
        "resource_title_or_link",
        "details",
        "contact_email",
        "reporter",
        "status",
        "resolution",
        "resolved_by",
        "resolved_at",
        "notification_sent_at",
        "notification_error",
        "submitted_at",
    )

    actions = (
        "resolve_and_republish",
        "confirm_removed",
        "dismiss_and_republish",
        "resend_reporter_notification",
    )

    ordering = ("-submitted_at",)
    list_per_page = 30

    fieldsets = (
        (
            "Report Information",
            {
                "fields": (
                    "resource",
                    "issue_type",
                    "course_code",
                    "resource_title_or_link",
                    "details",
                    "contact_email",
                    "reporter",
                    "submitted_at",
                )
            },
        ),
        (
            "Admin Response",
            {
                "fields": (
                    "admin_response",
                    "status",
                    "resolution",
                    "resolved_by",
                    "resolved_at",
                ),
                "description": (
                    "Optionally write a custom reply, save it, then use "
                    "one of the resolution actions from the report list."
                ),
            },
        ),
        (
            "Reporter Notification",
            {
                "fields": (
                    "notification_sent_at",
                    "notification_error",
                )
            },
        ),
    )

    @admin.display(description="Reference")
    def reference_code_display(self, obj):
        return obj.reference_code

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return _status_badge(obj.status, obj.get_status_display())

    @admin.display(description="Resource")
    def linked_resource(self, obj):
        if not obj.resource:
            return "—"

        url = reverse(
            "admin:resources_resource_change",
            args=[obj.resource_id],
        )
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.resource.title,
        )

    @admin.display(description="Notification")
    def notification_status(self, obj):
        if not obj.contact_email:
            return "No email"

        if obj.notification_sent_at:
            return "Sent"

        if obj.notification_error:
            return "Failed"

        if obj.status == "RESOLVED":
            return "Pending"

        return "Waiting"

    def _resolve_reports(self, request, queryset, resolution):
        resolved = 0
        without_resource = 0
        without_email = 0

        for report in queryset.select_related("resource"):
            if not report.resource_id:
                without_resource += 1

            if not report.contact_email:
                without_email += 1

            report.resolve(
                resolution=resolution,
                user=request.user,
            )
            resolved += 1

        self.message_user(
            request,
            (
                f"{resolved} report(s) resolved. "
                f"{without_email} had no reporter email. "
                f"{without_resource} had no linked resource."
            ),
        )

    @admin.action(
        description="Resolve: fix issue and republish resource"
    )
    def resolve_and_republish(self, request, queryset):
        self._resolve_reports(
            request,
            queryset,
            "REPUBLISHED",
        )

    @admin.action(
        description="Resolve: confirm removal and keep resource hidden"
    )
    def confirm_removed(self, request, queryset):
        self._resolve_reports(
            request,
            queryset,
            "REMOVED",
        )

    @admin.action(
        description="Dismiss report and republish resource"
    )
    def dismiss_and_republish(self, request, queryset):
        self._resolve_reports(
            request,
            queryset,
            "DISMISSED",
        )

    @admin.action(
        description="Resend resolution email to reporter"
    )
    def resend_reporter_notification(self, request, queryset):
        sent = 0
        skipped = 0

        for report in queryset:
            if (
                report.status != "RESOLVED"
                or not report.contact_email
            ):
                skipped += 1
                continue

            if send_report_resolution_email(report.pk):
                sent += 1
            else:
                skipped += 1

        self.message_user(
            request,
            (
                f"{sent} notification(s) sent. "
                f"{skipped} report(s) skipped or failed."
            ),
        )



@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = (
        "verified_email",
        "display_name",
        "email_verified_at",
        "created_at",
    )
    search_fields = ("verified_email", "display_name", "user__username")
    readonly_fields = (
        "user",
        "verified_email",
        "email_verified_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "purpose",
        "created_at",
        "expires_at",
        "attempts",
        "used_at",
        "request_ip",
    )
    list_filter = ("purpose", "created_at", "used_at")
    search_fields = ("email", "request_ip")
    readonly_fields = (
        "email",
        "purpose",
        "code_digest",
        "request_ip",
        "created_at",
        "expires_at",
        "used_at",
        "attempts",
    )

    def has_add_permission(self, request):
        return False


admin.site.site_header = "StudyBee administration"
admin.site.site_title = "StudyBee admin"
admin.site.index_title = "Moderation dashboard"
