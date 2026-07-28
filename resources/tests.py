from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Course, ReportIssue, Resource
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
            external_link="https://example.com/networks-slides",
        )

    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CSE421")
        self.assertContains(response, "CSE370")

    def test_home_search_matches_course_code(self):
        response = self.client.get(reverse("home"), {"q": "421"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CSE421")
        self.assertNotContains(response, "CSE370")

    def test_home_search_matches_course_title(self):
        response = self.client.get(reverse("home"), {"q": "database"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CSE370")
        self.assertNotContains(response, "CSE421")

    def test_home_context_contains_summary_values(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.context["total_courses"], 2)
        self.assertEqual(response.context["total_resources"], 1)
        self.assertEqual(
            response.context["latest_resource"].title,
            "Midterm Slides",
        )


class CourseDetailViewTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            course_code="CSE423",
            course_title="Computer Graphics",
        )

        self.slide = Resource.objects.create(
            course=self.course,
            title="Transformation Slides",
            category="SLIDE",
            exam_part="MIDTERM",
            description="Matrices and geometric transformations",
            external_link="https://example.com/transformation-slides",
        )

        self.note = Resource.objects.create(
            course=self.course,
            title="Rasterization Notes",
            category="NOTE",
            exam_part="FINAL",
            description="Line and circle drawing algorithms",
            external_link="https://example.com/rasterization-notes",
        )

        self.question = Resource.objects.create(
            course=self.course,
            title="Spring 2026 Midterm Question",
            category="QUESTION",
            question_type="PAST_EXAM",
            exam_part="MIDTERM",
            external_link="https://example.com/midterm-question",
        )

    def get_course(self, **params):
        return self.client.get(
            reverse("course_detail", args=[self.course.id]),
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
        self.assertNotContains(response, self.question.title)

    def test_syllabus_filter(self):
        response = self.get_course(exam_part="FINAL")

        self.assertContains(response, self.note.title)
        self.assertNotContains(response, self.slide.title)
        self.assertNotContains(response, self.question.title)

    def test_question_type_filter(self):
        response = self.get_course(
            category="QUESTION",
            question_type="PAST_EXAM",
        )

        self.assertContains(response, self.question.title)
        self.assertNotContains(response, self.slide.title)
        self.assertNotContains(response, self.note.title)

    def test_resource_search_matches_title(self):
        response = self.get_course(q="Rasterization")

        self.assertContains(response, self.note.title)
        self.assertNotContains(response, self.slide.title)

    def test_resource_search_matches_description(self):
        response = self.get_course(q="geometric transformations")

        self.assertContains(response, self.slide.title)
        self.assertNotContains(response, self.note.title)


    def test_course_resources_are_paginated(self):
        for index in range(30):
            Resource.objects.create(
                course=self.course,
                title=f"Extra Resource {index:02d}",
                category="NOTE",
                exam_part="GENERAL",
                external_link=f"https://example.com/resource-{index}",
            )

        first_page = self.get_course()
        second_page = self.get_course(page=2)

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(second_page.status_code, 200)
        self.assertTrue(first_page.context["page_obj"].has_next())
        self.assertEqual(first_page.context["page_obj"].number, 1)
        self.assertEqual(second_page.context["page_obj"].number, 2)
        self.assertLessEqual(
            len(first_page.context["page_obj"].object_list),
            10,
        )
        self.assertContains(
            first_page,
            "There are more resources.",
        )
        self.assertContains(first_page, "Next")
        self.assertContains(second_page, "Previous")

        rendered_html = first_page.content.decode("utf-8")
        resource_list_position = rendered_html.find(
            'class="resource-list"'
        )
        pagination_position = rendered_html.find(
            'class="resource-pagination-panel"'
        )

        self.assertGreater(
            pagination_position,
            resource_list_position,
        )

    def test_missing_course_returns_404(self):
        response = self.client.get(
            reverse("course_detail", args=[999999])
        )

        self.assertEqual(response.status_code, 404)


class ResourceModelValidationTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            course_code="CSE220",
            course_title="Data Structures",
        )

    def test_resource_requires_file_or_external_link(self):
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
            external_link="https://example.com/question",
        )

        with self.assertRaises(ValidationError) as context:
            resource.full_clean()

        self.assertIn("question_type", context.exception.message_dict)

    def test_non_question_cannot_have_solution(self):
        resource = Resource(
            course=self.course,
            title="Notes With Solution",
            category="NOTE",
            exam_part="GENERAL",
            external_link="https://example.com/notes",
            solution_link="https://example.com/solution",
        )

        with self.assertRaises(ValidationError):
            resource.full_clean()

    def test_valid_question_passes_validation(self):
        resource = Resource(
            course=self.course,
            title="Valid Question",
            category="QUESTION",
            question_type="PAST_EXAM",
            exam_part="MIDTERM",
            external_link="https://example.com/question",
            solution_link="https://example.com/solution",
        )

        resource.full_clean()


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
            content_type="application/octet-stream",
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

    def test_filename_sanitizer_removes_path_components(self):
        self.assertEqual(
            sanitize_filename(r"..\..\unsafe.pdf"),
            "unsafe.pdf",
        )


class ReportIssueViewTests(TestCase):
    def test_report_page_loads(self):
        response = self.client.get(reverse("report_issue"))

        self.assertEqual(response.status_code, 200)

    def test_valid_report_is_saved(self):
        response = self.client.post(
            reverse("report_issue"),
            {
                "issue_type": "BROKEN_LINK",
                "course_code": "CSE421",
                "resource_title_or_link": "Midterm Slides",
                "details": "The file link no longer opens.",
                "contact_email": "student@example.com",
                "next": reverse("home"),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ReportIssue.objects.count(), 1)

        report = ReportIssue.objects.get()
        self.assertEqual(report.course_code, "CSE421")
        self.assertEqual(report.status, "PENDING")

    def test_invalid_report_is_not_saved(self):
        response = self.client.post(
            reverse("report_issue"),
            {
                "issue_type": "BROKEN_LINK",
                "details": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ReportIssue.objects.count(), 0)

    def test_external_next_url_is_rejected(self):
        response = self.client.get(
            reverse("report_issue"),
            {"next": "https://example-evil.test/phishing"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["next_url"], reverse("home"))
