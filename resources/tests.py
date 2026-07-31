from io import BytesIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .importers import import_resources_from_csv
from .models import (
    Course,
    ReportIssue,
    Resource,
    ResourceSubmission,
)
from .validators import (
    MAX_FILE_SIZE,
    sanitize_filename,
    validate_resource_file,
)


class HomeViewTests(TestCase):
    def setUp(self):
        self.networks = Course.objects.create(
            course_code="CSE421",
            course_title="Computer Networks",
        )
        self.database = Course.objects.create(
            course_code="CSE370",
            course_title="Database Systems",
        )

        Resource.objects.create(
            course=self.networks,
            title="Midterm Slides",
            category="SLIDE",
            exam_part="MIDTERM",
            external_link=(
                "https://example.com/networks-slides"
            ),
        )

    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CSE421")
        self.assertContains(response, "CSE370")

    def test_home_search_matches_course_code(self):
        response = self.client.get(
            reverse("home"),
            {"q": "421"},
        )

        self.assertContains(response, "CSE421")
        self.assertNotContains(response, "CSE370")

    def test_home_search_form_has_server_fallback(self):
        response = self.client.get(reverse("home"))

        self.assertContains(
            response,
            'name="q"',
        )
        self.assertContains(
            response,
            reverse("global_search"),
        )


class GlobalSearchTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            course_code="CSE260",
            course_title="Digital Logic Design",
        )
        self.resource = Resource.objects.create(
            course=self.course,
            title="Karnaugh Map Notes",
            category="NOTE",
            exam_part="MIDTERM",
            semester_term="SUMMER",
            semester_year=2026,
            external_link=(
                "https://example.com/kmap-notes"
            ),
        )

    def test_global_search_finds_resource(self):
        response = self.client.get(
            reverse("global_search"),
            {"q": "Karnaugh"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.resource.title)
        self.assertContains(response, self.course.course_code)

    def test_global_search_hides_needs_review_resources(self):
        self.resource.verification_status = "NEEDS_REVIEW"
        self.resource.save()

        response = self.client.get(
            reverse("global_search"),
            {"q": "Karnaugh"},
        )

        self.assertNotContains(response, self.resource.title)

    def test_global_search_filters_semester(self):
        response = self.client.get(
            reverse("global_search"),
            {
                "q": "Notes",
                "semester_term": "SUMMER",
                "semester_year": "2026",
            },
        )

        self.assertContains(response, self.resource.title)

        other_response = self.client.get(
            reverse("global_search"),
            {
                "q": "Notes",
                "semester_term": "FALL",
            },
        )

        self.assertNotContains(
            other_response,
            self.resource.title,
        )


class CourseDetailViewTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            course_code="CSE423",
            course_title="Computer Graphics",
        )
        self.prerequisite = Course.objects.create(
            course_code="CSE220",
            course_title="Data Structures",
        )
        self.course.hard_prerequisite = "CSE220"
        self.course.save()

        self.slide = Resource.objects.create(
            course=self.course,
            title="Transformation Slides",
            category="SLIDE",
            exam_part="MIDTERM",
            description=(
                "Matrices and geometric transformations"
            ),
            external_link=(
                "https://example.com/transformation-slides"
            ),
        )

        self.note = Resource.objects.create(
            course=self.course,
            title="Rasterization Notes",
            category="NOTE",
            exam_part="FINAL",
            semester_term="FALL",
            semester_year=2026,
            description=(
                "Line and circle drawing algorithms"
            ),
            external_link=(
                "https://example.com/rasterization-notes"
            ),
        )

        self.question = Resource.objects.create(
            course=self.course,
            title="Spring 2026 Midterm Question",
            category="QUESTION",
            question_type="PAST_EXAM",
            exam_part="MIDTERM",
            external_link=(
                "https://example.com/midterm-question"
            ),
        )

    def get_course(self, **params):
        return self.client.get(
            reverse(
                "course_detail",
                kwargs={
                    "course_code": (
                        self.course.course_code.lower()
                    ),
                },
            ),
            params,
        )

    def test_course_page_loads(self):
        response = self.get_course()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.slide.title)
        self.assertContains(response, self.note.title)
        self.assertContains(response, self.question.title)

    def test_category_filter(self):
        response = self.get_course(category="SLIDE")

        self.assertContains(response, self.slide.title)
        self.assertNotContains(response, self.note.title)

    def test_syllabus_filter(self):
        response = self.get_course(exam_part="FINAL")

        self.assertContains(response, self.note.title)
        self.assertNotContains(response, self.slide.title)

    def test_semester_filter(self):
        response = self.get_course(
            semester_term="FALL",
            semester_year="2026",
        )

        self.assertContains(response, self.note.title)
        self.assertNotContains(response, self.slide.title)

    def test_focus_resource_from_global_search(self):
        response = self.get_course(
            focus=self.note.id,
        )

        self.assertContains(response, self.note.title)
        self.assertNotContains(response, self.slide.title)
        self.assertContains(
            response,
            "Showing one selected search result.",
        )

    def test_prerequisite_is_linked(self):
        response = self.get_course()

        prerequisite_url = reverse(
            "course_detail",
            kwargs={
                "course_code": (
                    self.prerequisite.course_code.lower()
                ),
            },
        )

        self.assertContains(response, prerequisite_url)

    def test_sections_are_alphabetical(self):
        response = self.get_course()

        names = [
            section["name"]
            for section in response.context[
                "grouped_resources"
            ]
        ]

        self.assertEqual(
            names,
            sorted(names, key=str.lower),
        )

    def test_course_resources_are_paginated(self):
        for index in range(30):
            Resource.objects.create(
                course=self.course,
                title=f"Extra Resource {index:02d}",
                category="NOTE",
                exam_part="GENERAL",
                external_link=(
                    f"https://example.com/resource-{index}"
                ),
            )

        first_page = self.get_course()
        second_page = self.get_course(page=2)

        self.assertTrue(
            first_page.context["page_obj"].has_next()
        )
        self.assertEqual(
            len(
                first_page.context[
                    "page_obj"
                ].object_list
            ),
            10,
        )
        self.assertContains(
            first_page,
            "There are more resources.",
        )
        self.assertContains(second_page, "Previous")

        rendered = first_page.content.decode("utf-8")

        self.assertGreater(
            rendered.find(
                'class="resource-pagination-panel"'
            ),
            rendered.find(
                'class="resource-list"'
            ),
        )

    def test_missing_course_returns_404(self):
        response = self.client.get(
            reverse(
                "course_detail",
                kwargs={
                    "course_code": "missing-course",
                },
            )
        )

        self.assertEqual(response.status_code, 404)


class ResourceModelValidationTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            course_code="CSE220",
            course_title="Data Structures",
        )

    def test_resource_requires_file_or_link(self):
        resource = Resource(
            course=self.course,
            title="Missing Material",
            category="NOTE",
            exam_part="GENERAL",
        )

        with self.assertRaises(ValidationError):
            resource.full_clean()

    def test_question_requires_question_type(self):
        resource = Resource(
            course=self.course,
            title="Question Without Type",
            category="QUESTION",
            exam_part="MIDTERM",
            external_link=(
                "https://example.com/question"
            ),
        )

        with self.assertRaises(ValidationError):
            resource.full_clean()

    def test_structured_semester_requires_pair(self):
        resource = Resource(
            course=self.course,
            title="Incomplete Semester",
            category="NOTE",
            exam_part="GENERAL",
            semester_term="SPRING",
            external_link="https://example.com/notes",
        )

        with self.assertRaises(ValidationError):
            resource.full_clean()

    def test_semester_display(self):
        resource = Resource.objects.create(
            course=self.course,
            title="Structured Semester",
            category="NOTE",
            exam_part="GENERAL",
            semester_term="SUMMER",
            semester_year=2026,
            external_link="https://example.com/notes",
        )

        self.assertEqual(
            resource.semester_display,
            "Summer 2026",
        )


class UploadValidatorTests(TestCase):
    def test_allowed_pdf_is_accepted(self):
        uploaded = SimpleUploadedFile(
            "lecture.pdf",
            b"%PDF-1.4 test",
            content_type="application/pdf",
        )

        validate_resource_file(uploaded)

    def test_unsupported_extension_is_rejected(self):
        uploaded = SimpleUploadedFile(
            "script.exe",
            b"not an executable",
            content_type=(
                "application/octet-stream"
            ),
        )

        with self.assertRaises(ValidationError):
            validate_resource_file(uploaded)

    def test_file_above_limit_is_rejected(self):
        uploaded = SimpleUploadedFile(
            "large.pdf",
            b"small test content",
            content_type="application/pdf",
        )
        uploaded.size = MAX_FILE_SIZE + 1

        with self.assertRaises(ValidationError):
            validate_resource_file(uploaded)

    def test_filename_sanitizer(self):
        self.assertEqual(
            sanitize_filename(
                r"..\..\unsafe.pdf"
            ),
            "unsafe.pdf",
        )


class StudentSubmissionTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            course_code="CSE330",
            course_title="Numerical Methods",
        )

    def test_submission_page_loads(self):
        response = self.client.get(
            reverse("submit_resource")
        )

        self.assertEqual(response.status_code, 200)

    def test_valid_submission_is_pending(self):
        response = self.client.post(
            reverse("submit_resource"),
            {
                "course": self.course.id,
                "title": "Student Notes",
                "category": "NOTE",
                "exam_part": "MIDTERM",
                "question_type": "",
                "semester_term": "SUMMER",
                "semester_year": "2026",
                "description": "Shared notes",
                "external_link": (
                    "https://example.com/student-notes"
                ),
                "solution_link": "",
                "submitter_name": "Student",
                "submitter_email": (
                    "student@example.com"
                ),
                "note_to_admin": "Shared in class",
                "website": "",
            },
        )

        self.assertRedirects(
            response,
            reverse("submit_resource_success"),
        )

        submission = ResourceSubmission.objects.get()

        self.assertEqual(
            submission.status,
            "PENDING",
        )
        self.assertFalse(
            Resource.objects.filter(
                title="Student Notes"
            ).exists()
        )

    def test_admin_approval_creates_public_unverified_resource(
        self,
    ):
        submission = ResourceSubmission.objects.create(
            course=self.course,
            title="Approved Notes",
            category="NOTE",
            exam_part="GENERAL",
            external_link=(
                "https://example.com/approved"
            ),
        )
        user = get_user_model().objects.create_user(
            username="reviewer",
            password="test-password",
        )

        resource = submission.approve(user=user)

        self.assertEqual(
            submission.status,
            "APPROVED",
        )
        self.assertEqual(
            resource.verification_status,
            "UNVERIFIED",
        )
        self.assertIsNone(resource.verified_by)
        self.assertEqual(
            submission.published_resource,
            resource,
        )

        course_response = self.client.get(
            reverse(
                "course_detail",
                kwargs={
                    "course_code": (
                        self.course.course_code.lower()
                    ),
                },
            )
        )

        self.assertContains(
            course_response,
            resource.title,
        )
        self.assertNotContains(
            course_response,
            "Verified",
        )

    def test_manually_approved_submission_can_be_repaired(self):
        submission = ResourceSubmission.objects.create(
            course=self.course,
            title="Repair Me",
            category="NOTE",
            exam_part="GENERAL",
            external_link="https://example.com/repair-me",
            status="APPROVED",
        )

        first_resource = submission.approve()
        second_resource = submission.approve()

        submission.refresh_from_db()

        self.assertEqual(first_resource, second_resource)
        self.assertEqual(
            submission.published_resource,
            first_resource,
        )
        self.assertEqual(
            Resource.objects.filter(
                title="Repair Me"
            ).count(),
            1,
        )


class ReportIssueViewTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            course_code="CSE421",
            course_title="Computer Networks",
        )
        self.resource = Resource.objects.create(
            course=self.course,
            title="Midterm Slides",
            category="SLIDE",
            exam_part="MIDTERM",
            verification_status="VERIFIED",
            external_link=(
                "https://example.com/slides"
            ),
        )

    def test_valid_linked_broken_report_marks_review(self):
        response = self.client.post(
            reverse("report_issue"),
            {
                "resource": self.resource.id,
                "issue_type": "BROKEN_LINK",
                "course_code": self.course.course_code,
                "resource_title_or_link": (
                    self.resource.title
                ),
                "details": "The link no longer opens.",
                "contact_email": "",
                "next": reverse("home"),
            },
        )

        self.assertEqual(response.status_code, 302)

        report = ReportIssue.objects.get()
        self.resource.refresh_from_db()

        self.assertEqual(
            report.resource,
            self.resource,
        )
        self.assertEqual(
            self.resource.verification_status,
            "NEEDS_REVIEW",
        )

        course_response = self.client.get(
            reverse(
                "course_detail",
                kwargs={
                    "course_code": (
                        self.course.course_code.lower()
                    ),
                },
            )
        )

        self.assertNotContains(
            course_response,
            self.resource.title,
        )

    def test_external_next_url_is_rejected(self):
        response = self.client.get(
            reverse("report_issue"),
            {
                "next": (
                    "https://example-evil.test/phishing"
                )
            },
        )

        self.assertEqual(
            response.context["next_url"],
            reverse("home"),
        )


class BulkImportTests(TestCase):
    def test_csv_import_creates_course_and_resource(self):
        csv_bytes = (
            "course_code,course_title,title,category,"
            "external_link,semester_term,semester_year,"
            "verification_status\n"
            "CSE460,Introduction to Robotics,"
            "Robot Notes,NOTE,"
            "https://example.com/robot-notes,"
            "SUMMER,2026,VERIFIED\n"
        ).encode("utf-8")

        result = import_resources_from_csv(
            BytesIO(csv_bytes)
        )

        self.assertEqual(
            result["created_courses"],
            1,
        )
        self.assertEqual(
            result["created_resources"],
            1,
        )

        resource = Resource.objects.get(
            title="Robot Notes"
        )
        self.assertEqual(
            resource.course.course_code,
            "CSE460",
        )
        self.assertEqual(
            resource.semester_display,
            "Summer 2026",
        )

        response = self.client.get(
            reverse(
                "course_detail",
                kwargs={
                    "course_code": (
                        resource.course.course_code.lower()
                    ),
                },
            )
        )

        self.assertContains(response, resource.title)


@override_settings(
    EMAIL_BACKEND=(
        "django.core.mail.backends.locmem.EmailBackend"
    ),
    DEFAULT_FROM_EMAIL=(
        "StudyBee <studybee@example.com>"
    ),
)
class ReportIssueResolutionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="moderator",
            password="test-password",
        )
        self.course = Course.objects.create(
            course_code="CSE260",
            course_title="Digital Logic Design",
        )
        self.resource = Resource.objects.create(
            course=self.course,
            title="Community Notes",
            category="NOTE",
            exam_part="GENERAL",
            external_link=(
                "https://example.com/community-notes"
            ),
            verification_status="NEEDS_REVIEW",
        )

    def create_report(
        self,
        email="student@example.com",
    ):
        return ReportIssue.objects.create(
            resource=self.resource,
            issue_type="BROKEN_LINK",
            details="The link does not open.",
            contact_email=email,
        )

    def test_resolve_and_republish_restores_resource_and_emails(
        self,
    ):
        report = self.create_report()

        with self.captureOnCommitCallbacks(execute=True):
            report.resolve(
                "REPUBLISHED",
                user=self.user,
            )

        report.refresh_from_db()
        self.resource.refresh_from_db()

        self.assertEqual(
            report.status,
            "RESOLVED",
        )
        self.assertEqual(
            report.resolution,
            "REPUBLISHED",
        )
        self.assertEqual(
            self.resource.verification_status,
            "UNVERIFIED",
        )
        self.assertIsNotNone(
            report.notification_sent_at
        )
        self.assertEqual(
            len(mail.outbox),
            1,
        )
        self.assertIn(
            "publicly available again",
            mail.outbox[0].body,
        )

    def test_confirm_removed_keeps_resource_hidden_and_emails(
        self,
    ):
        report = self.create_report()

        with self.captureOnCommitCallbacks(execute=True):
            report.resolve(
                "REMOVED",
                user=self.user,
            )

        report.refresh_from_db()
        self.resource.refresh_from_db()

        self.assertEqual(
            report.resolution,
            "REMOVED",
        )
        self.assertEqual(
            self.resource.verification_status,
            "BROKEN",
        )
        self.assertEqual(
            len(mail.outbox),
            1,
        )
        self.assertIn(
            "removed from the public StudyBee site",
            mail.outbox[0].body,
        )

    def test_report_without_email_resolves_without_notification(
        self,
    ):
        report = self.create_report(email="")

        with self.captureOnCommitCallbacks(execute=True):
            report.resolve(
                "DISMISSED",
                user=self.user,
            )

        report.refresh_from_db()

        self.assertEqual(
            report.status,
            "RESOLVED",
        )
        self.assertIsNone(
            report.notification_sent_at
        )
        self.assertEqual(
            report.notification_error,
            "",
        )
        self.assertEqual(
            len(mail.outbox),
            0,
        )