from io import BytesIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .authentication import student_is_verified
from .importers import import_resources_from_csv
from .models import (
    Course,
    EmailVerificationCode,
    ReportIssue,
    Resource,
    ResourceSubmission,
    StudentProfile,
    student_name_from_email,
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

    def test_home_uses_compact_two_line_hero_copy(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "Your course resources,")
        self.assertContains(response, "organized in one place.")
        self.assertNotContains(response, "shape-four")

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

    def test_primary_navigation_separates_home_and_courses(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, ">Home</a>", html=False)
        self.assertContains(response, 'href="/#course-directory">Courses</a>')
        self.assertNotContains(
            response,
            'data-modal-open="report">Report</a>',
        )

    def test_footer_keeps_only_support_links(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "footer-primary-links")
        self.assertContains(response, ">About</a>")
        self.assertContains(response, ">Report an issue</a>")
        self.assertContains(response, ">Privacy</a>")
        self.assertContains(response, ">Terms</a>")
        self.assertNotContains(response, ">Explore</strong>")

        # The header legitimately contains <strong>StudyBee</strong> as the
        # main brand. Only check the footer so the test targets the duplicate
        # footer heading that this UI change removed.
        footer_html = response.content.decode("utf-8").split(
            '<footer class="site-footer">',
            1,
        )[1]
        self.assertNotIn("<strong>StudyBee</strong>", footer_html)


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

    def test_course_filters_omit_semester_controls(self):
        response = self.get_course()

        self.assertNotContains(response, "<p>Semester</p>", html=False)
        self.assertContains(response, "Fall 2026")
        self.assertContains(response, 'class="title-line"')

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


class StudentIdentityTests(TestCase):
    def test_name_is_derived_from_email_separators(self):
        self.assertEqual(
            student_name_from_email(
                "zarrin.tasnim-rodela_student@g.bracu.ac.bd"
            ),
            "Zarrin Tasnim Rodela Student",
        )

    def test_profile_uses_readable_email_name(self):
        user = get_user_model().objects.create_user(
            username="named-student",
            email="zarrin.tasnim.rodela@g.bracu.ac.bd",
        )
        profile = StudentProfile.objects.create(
            user=user,
            verified_email=user.email,
            display_name="Old Name",
        )

        self.assertEqual(profile.display_name, "Zarrin Tasnim Rodela")

    @override_settings(BRACU_ALLOWED_EMAIL_DOMAIN="g.bracu.ac.bd")
    def test_non_bracu_profile_is_not_verified(self):
        user = get_user_model().objects.create_user(
            username="legacy-gmail-student",
            email="student@gmail.com",
        )
        StudentProfile.objects.create(
            user=user,
            verified_email=user.email,
        )

        self.assertFalse(student_is_verified(user))

    @override_settings(BRACU_ALLOWED_EMAIL_DOMAIN="g.bracu.ac.bd")
    def test_non_bracu_legacy_session_shows_login_not_student_account(self):
        user = get_user_model().objects.create_user(
            username="legacy-session",
            email="legacy@gmail.com",
        )
        StudentProfile.objects.create(
            user=user,
            verified_email=user.email,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Log in / Sign up")
        self.assertNotContains(response, "My StudyBee")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="StudyBee <studybee@example.com>",
    BREVO_API_KEY="",
    BREVO_SENDER_EMAIL="",
    BRACU_ALLOWED_EMAIL_DOMAIN="g.bracu.ac.bd",
    STUDENT_PASSWORD_MIN_LENGTH=8,
)
class StudentAccountAccessTests(TestCase):
    password = "Correct horse battery staple 2026!"

    def extract_code(self):
        import re
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def create_verified_user(self, email="student@g.bracu.ac.bd", password=None):
        user = get_user_model().objects.create_user(
            username=email,
            email=email,
            password=password or self.password,
        )
        StudentProfile.objects.create(
            user=user,
            verified_email=email,
        )
        return user

    def test_non_bracu_signup_email_is_rejected(self):
        response = self.client.post(
            reverse("student_signup_request"),
            {"email": "student@gmail.com"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("@g.bracu.ac.bd", str(response.json()["errors"]))
        self.assertFalse(EmailVerificationCode.objects.exists())

    def test_signup_verifies_email_and_creates_password_account(self):
        email = "new.student@g.bracu.ac.bd"
        response = self.client.post(
            reverse("student_signup_request"),
            {"email": email, "next": reverse("submit_resource")},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(len(mail.outbox), 1)
        code = self.extract_code()
        otp = EmailVerificationCode.objects.get(email=email)
        self.assertEqual(otp.purpose, "SIGNUP")

        response = self.client.post(
            reverse("student_signup_complete"),
            {
                "code": code,
                "password1": self.password,
                "password2": self.password,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["redirect"], reverse("submit_resource"))
        user = get_user_model().objects.get(email=email)
        self.assertTrue(user.check_password(self.password))
        self.assertTrue(student_is_verified(user))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_login_uses_password_and_does_not_send_code(self):
        user = self.create_verified_user()
        mail.outbox.clear()
        response = self.client.post(
            reverse("student_login"),
            {
                "email": user.email,
                "password": self.password,
                "remember_me": "on",
                "next": reverse("student_account"),
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_wrong_password_is_rejected(self):
        user = self.create_verified_user()
        response = self.client.post(
            reverse("student_login"),
            {"email": user.email, "password": "wrong-password"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_reset_uses_code_then_sets_new_password(self):
        user = self.create_verified_user()
        new_password = "A newer memorable StudyBee password 2026!"
        response = self.client.post(
            reverse("student_password_reset_request"),
            {"email": user.email},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        code = self.extract_code()
        otp = EmailVerificationCode.objects.get(email=user.email)
        self.assertEqual(otp.purpose, "PASSWORD_RESET")

        response = self.client.post(
            reverse("student_password_reset_complete"),
            {
                "code": code,
                "password1": new_password,
                "password2": new_password,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_legacy_passwordless_student_can_finish_signup(self):
        email = "legacy.student@g.bracu.ac.bd"
        user = get_user_model().objects.create_user(
            username=email,
            email=email,
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        StudentProfile.objects.create(user=user, verified_email=email)

        response = self.client.post(
            reverse("student_signup_request"),
            {"email": email},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        code = self.extract_code()
        response = self.client.post(
            reverse("student_signup_complete"),
            {
                "code": code,
                "password1": self.password,
                "password2": self.password,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.password))

    def test_account_popup_uses_login_signup_and_password_language(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Don’t have an account?")
        self.assertContains(response, "Send sign-up code")
        self.assertContains(response, "Forgot password?")
        self.assertNotContains(response, "Email me a login code")

    def test_eight_character_password_is_accepted(self):
        email = "eight.chars@g.bracu.ac.bd"
        self.client.post(
            reverse("student_signup_request"),
            {"email": email},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        code = self.extract_code()
        response = self.client.post(
            reverse("student_signup_complete"),
            {
                "code": code,
                "password1": "BeeHive8",
                "password2": "BeeHive8",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_seven_character_password_is_rejected(self):
        email = "seven.chars@g.bracu.ac.bd"
        self.client.post(
            reverse("student_signup_request"),
            {"email": email},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        code = self.extract_code()
        response = self.client.post(
            reverse("student_signup_complete"),
            {
                "code": code,
                "password1": "Bee1234",
                "password2": "Bee1234",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("at least 8", str(response.json()["errors"]).lower())


class StudentSubmissionTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            course_code="CSE330",
            course_title="Numerical Methods",
        )
        self.student = get_user_model().objects.create_user(
            username="student@g.bracu.ac.bd",
            email="student@g.bracu.ac.bd",
        )
        self.student.set_unusable_password()
        self.student.save()
        StudentProfile.objects.create(
            user=self.student,
            verified_email=self.student.email,
            display_name="Student",
        )

    def test_anonymous_student_is_sent_to_login(self):
        response = self.client.get(reverse("submit_resource"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("home"), response.url)
        self.assertIn("auth=1", response.url)
        self.assertIn("next=%2Fsubmit%2F", response.url)

    def test_submission_page_loads_for_verified_student(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("submit_resource"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.email)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        BREVO_API_KEY="",
        BREVO_SENDER_EMAIL="",
    )
    def test_valid_submission_is_pending(self):
        self.client.force_login(self.student)
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
                "external_link": "https://example.com/student-notes",
                "solution_link": "",
                "note_to_admin": "Shared in class",
                "website": "",
            },
        )
        self.assertRedirects(response, reverse("submit_resource_success"))
        submission = ResourceSubmission.objects.get()
        self.assertEqual(submission.status, "PENDING")
        self.assertEqual(submission.submitted_by, self.student)
        self.assertEqual(submission.submitter_email, self.student.email)
        self.assertFalse(Resource.objects.filter(title="Student Notes").exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_admin_approval_creates_public_unverified_resource(self):
        submission = ResourceSubmission.objects.create(
            course=self.course,
            title="Approved Notes",
            category="NOTE",
            exam_part="GENERAL",
            external_link="https://example.com/approved",
        )
        user = get_user_model().objects.create_user(
            username="reviewer",
            password="test-password",
        )
        resource = submission.approve(user=user)
        self.assertEqual(submission.status, "APPROVED")
        self.assertEqual(resource.verification_status, "UNVERIFIED")
        self.assertIsNone(resource.verified_by)
        self.assertEqual(submission.published_resource, resource)
        course_response = self.client.get(
            reverse(
                "course_detail",
                kwargs={"course_code": self.course.course_code.lower()},
            )
        )
        self.assertContains(course_response, resource.title)
        self.assertNotContains(course_response, "Verified")

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
        self.assertEqual(submission.published_resource, first_resource)
        self.assertEqual(Resource.objects.filter(title="Repair Me").count(), 1)


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

    def test_popup_report_returns_json_reference(self):
        response = self.client.post(
            reverse("report_issue"),
            {
                "resource": self.resource.id,
                "issue_type": "BROKEN_LINK",
                "course_code": self.course.course_code,
                "resource_title_or_link": self.resource.title,
                "details": "The popup report says the link is broken.",
                "contact_email": "",
                "next": reverse("home"),
                "website": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(response.json()["reference"])
        self.assertEqual(ReportIssue.objects.count(), 1)


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

@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="StudyBee <studybee@example.com>",
    BREVO_API_KEY="",
    BREVO_SENDER_EMAIL="",
)
class StudentWorkflowEmailTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            course_code="CSE250",
            course_title="Circuits and Electronics",
        )
        self.student = get_user_model().objects.create_user(
            username="workflow-student",
            email="workflow@g.bracu.ac.bd",
        )
        StudentProfile.objects.create(
            user=self.student,
            verified_email=self.student.email,
            display_name="Workflow Student",
        )

    def make_submission(self):
        return ResourceSubmission.objects.create(
            course=self.course,
            submitted_by=self.student,
            submitter_name="Workflow Student",
            submitter_email=self.student.email,
            title="Circuit Notes",
            category="NOTE",
            exam_part="GENERAL",
            external_link="https://example.com/circuit-notes",
        )

    def test_approval_sends_student_update(self):
        submission = self.make_submission()

        with self.captureOnCommitCallbacks(execute=True):
            submission.approve()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("approved and published", mail.outbox[0].body)
        self.assertIn(submission.reference_code, mail.outbox[0].body)

    def test_rejection_sends_review_note(self):
        submission = self.make_submission()
        submission.review_notes = "Please provide a working public link."
        submission.save(update_fields=["review_notes"])

        with self.captureOnCommitCallbacks(execute=True):
            submission.reject()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("not approved", mail.outbox[0].body)
        self.assertIn("working public link", mail.outbox[0].body)

    def test_verified_report_uses_account_email_and_sends_receipt(self):
        resource = Resource.objects.create(
            course=self.course,
            title="Old Slides",
            category="SLIDE",
            exam_part="MIDTERM",
            external_link="https://example.com/old-slides",
        )
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("report_issue"),
            {
                "resource": resource.pk,
                "issue_type": "BROKEN_LINK",
                "course_code": self.course.course_code,
                "resource_title_or_link": resource.title,
                "details": "The link returns an error.",
                "contact_email": "spoofed@example.com",
                "website": "",
                "next": reverse("home"),
            },
        )

        self.assertEqual(response.status_code, 302)
        report = ReportIssue.objects.get()
        self.assertEqual(report.reporter, self.student)
        self.assertEqual(report.contact_email, self.student.email)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(report.reference_code, mail.outbox[0].body)


class CoursePolishTests(TestCase):
    def test_course_page_has_access_note_and_matching_lab_pill(self):
        course = Course.objects.create(
            course_code="CSE260",
            course_title="Digital Logic Design",
            hard_prerequisite="CSE110",
            lab_type="NO_LAB",
        )

        response = self.client.get(
            reverse(
                "course_detail",
                kwargs={"course_code": course.course_code.lower()},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Some Drive links may require your BRACU GSuite account.",
        )
        self.assertContains(response, 'class="lab-pill"')
