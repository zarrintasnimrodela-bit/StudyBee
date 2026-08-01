import hashlib
import re
from datetime import timedelta
from urllib.parse import urlencode
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.paginator import Paginator
from django.db.models import Case, Count, F, IntegerField, Q, When
from django.db.models.functions import Lower
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse
from django.utils import timezone
from django.utils.http import (
    url_has_allowed_host_and_scheme,
)
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters

from .authentication import (
    client_ip,
    student_is_verified,
    verified_student_required,
)
from .forms import (
    ReportIssueForm,
    ResourceSubmissionForm,
    StudentCodePasswordForm,
    StudentEmailForm,
    StudentLoginForm,
)
from .models import (
    Course,
    EmailVerificationCode,
    ReportIssue,
    Resource,
    ResourceSubmission,
    SEMESTER_TERM_CHOICES,
    StudentProfile,
    student_name_from_email,
)
from .notifications import (
    send_account_code_email,
    send_report_received_email,
    send_submission_received_email,
)


PUBLIC_RESOURCE_STATUSES = (
    "UNVERIFIED",
    "VERIFIED",
)


def _wants_json(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _form_error_payload(form):
    return {
        field: [str(message) for message in messages]
        for field, messages in form.errors.items()
    }


def _public_resources(queryset):
    return queryset.filter(
        verification_status__in=PUBLIC_RESOURCE_STATUSES
    )


def _pagination_items(paginator, current_page):
    items = []

    for page_number in paginator.get_elided_page_range(
        current_page,
        on_each_side=1,
        on_ends=1,
    ):
        if page_number == paginator.ELLIPSIS:
            items.append({"ellipsis": True})
        else:
            items.append(
                {
                    "number": page_number,
                    "current": page_number == current_page,
                }
            )

    return items


def _pagination_query(request):
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


def _parse_prerequisite_codes(value):
    return [
        part.strip().upper()
        for part in re.split(r"[,;/]+", value or "")
        if part.strip()
    ]


def _prerequisite_links(value, course_lookup):
    links = []

    for code in _parse_prerequisite_codes(value):
        linked_course = course_lookup.get(code)

        links.append(
            {
                "code": code,
                "course": linked_course,
            }
        )

    return links


def home(request):
    query = request.GET.get("q", "").strip()

    courses = Course.objects.annotate(
        resource_count=Count(
            "resources",
            filter=Q(
                resources__verification_status__in=(
                    PUBLIC_RESOURCE_STATUSES
                )
            ),
        )
    ).order_by("course_code")

    if query:
        courses = courses.filter(
            Q(course_code__icontains=query)
            | Q(course_title__icontains=query)
        )

    return render(
        request,
        "resources/home.html",
        {
            "courses": courses,
            "query": query,
        },
    )


def global_search(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    semester_term = request.GET.get(
        "semester_term",
        "",
    ).strip()
    semester_year = request.GET.get(
        "semester_year",
        "",
    ).strip()

    courses = Course.objects.none()
    resources = Resource.objects.none()

    if query:
        courses = Course.objects.annotate(
            resource_count=Count(
                "resources",
                filter=Q(
                    resources__verification_status__in=(
                        PUBLIC_RESOURCE_STATUSES
                    )
                ),
            )
        ).filter(
            Q(course_code__icontains=query)
            | Q(course_title__icontains=query)
        ).order_by("course_code")

        resources = _public_resources(
            Resource.objects.select_related("course")
        ).filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(course__course_code__icontains=query)
            | Q(course__course_title__icontains=query)
            | Q(semester__icontains=query)
        )

        if category:
            resources = resources.filter(category=category)

        if semester_term:
            resources = resources.filter(
                semester_term=semester_term
            )

        if semester_year.isdigit():
            resources = resources.filter(
                semester_year=int(semester_year)
            )

        resources = resources.order_by(
            "course__course_code",
            Lower("title"),
        )

    paginator = Paginator(resources, 20)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    available_years = (
        _public_resources(Resource.objects.all()).exclude(
            semester_year__isnull=True
        )
        .values_list("semester_year", flat=True)
        .distinct()
        .order_by("-semester_year")
    )

    return render(
        request,
        "resources/global_search.html",
        {
            "query": query,
            "courses": courses[:12],
            "page_obj": page_obj,
            "resources": page_obj.object_list,
            "category": category,
            "semester_term": semester_term,
            "semester_year": semester_year,
            "category_choices": Resource.CATEGORY_CHOICES,
            "semester_term_choices": SEMESTER_TERM_CHOICES,
            "available_years": available_years,
            "pagination_items": _pagination_items(
                paginator,
                page_obj.number,
            ),
            "pagination_query": _pagination_query(request),
        },
    )


def legacy_course_detail(request, course_id):
    """
    Redirect old numeric course URLs to clean course-code URLs.

    Example:
    /course/13/ -> /course/cse423/
    """
    course = get_object_or_404(
        Course,
        id=course_id,
    )

    destination = reverse(
        "course_detail",
        kwargs={
            "course_code": course.course_code.lower(),
        },
    )

    query_string = request.META.get(
        "QUERY_STRING",
        "",
    )

    if query_string:
        destination = f"{destination}?{query_string}"

    return redirect(
        destination,
        permanent=True,
    )


def course_detail(request, course_code):
    course = get_object_or_404(
        Course,
        course_code__iexact=course_code,
    )

    all_resources_count = _public_resources(
        course.resources.all()
    ).count()

    exam_part = request.GET.get("exam_part", "")
    category = request.GET.get("category", "")
    question_type = request.GET.get(
        "question_type",
        "",
    )
    search_query = request.GET.get("q", "").strip()
    focus_resource = request.GET.get("focus", "").strip()

    resources = _public_resources(
        course.resources.all()
    )

    if focus_resource.isdigit():
        resources = resources.filter(pk=int(focus_resource))
    else:
        if exam_part:
            resources = resources.filter(
                exam_part=exam_part
            )

        if category:
            resources = resources.filter(
                category=category
            )

        if question_type:
            resources = resources.filter(
                question_type=question_type
            )

        if search_query:
            resources = resources.filter(
                Q(title__icontains=search_query)
                | Q(description__icontains=search_query)
            )

    alphabetical_categories = sorted(
        Resource.CATEGORY_CHOICES,
        key=lambda choice: choice[1].lower(),
    )

    category_order = Case(
        *[
            When(
                category=category_code,
                then=position,
            )
            for position, (
                category_code,
                _category_label,
            ) in enumerate(alphabetical_categories)
        ],
        default=len(alphabetical_categories),
        output_field=IntegerField(),
    )

    resources = resources.annotate(
        category_sort=category_order
    ).order_by(
        "category_sort",
        Lower("title"),
    )

    paginator = Paginator(resources, 10)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )
    page_resources = list(page_obj.object_list)

    resources_by_category = defaultdict(list)

    for resource in page_resources:
        resources_by_category[
            resource.category
        ].append(resource)

    previous_category = None
    next_category = None

    if page_obj.has_previous():
        previous_index = page_obj.start_index() - 2
        previous_category = resources.values_list(
            "category",
            flat=True,
        )[previous_index]

    if page_obj.has_next():
        next_index = page_obj.end_index()
        next_category = resources.values_list(
            "category",
            flat=True,
        )[next_index]

    grouped_resources = []

    for (
        category_code,
        category_label,
    ) in alphabetical_categories:
        section_resources = resources_by_category.get(
            category_code
        )

        if not section_resources:
            continue

        grouped_resources.append(
            {
                "name": category_label,
                "resources": section_resources,
                "continued_from_previous": (
                    previous_category == category_code
                ),
                "continues_next": (
                    next_category == category_code
                ),
            }
        )

    course_lookup = {
        item.course_code.upper(): item
        for item in Course.objects.only(
            "id",
            "course_code",
            "course_title",
        )
    }

    return render(
        request,
        "resources/course_detail.html",
        {
            "course": course,
            "resources": page_resources,
            "grouped_resources": grouped_resources,
            "page_obj": page_obj,
            "pagination_items": _pagination_items(
                paginator,
                page_obj.number,
            ),
            "pagination_query": _pagination_query(
                request
            ),
            "remaining_resources": (
                paginator.count
                - page_obj.end_index()
            ),
            "all_resources_count": (
                all_resources_count
            ),
            "exam_part": exam_part,
            "category": category,
            "question_type": question_type,
            "search_query": search_query,
            "focus_resource": focus_resource,
            "hard_prerequisites": (
                _prerequisite_links(
                    course.hard_prerequisite,
                    course_lookup,
                )
            ),
            "soft_prerequisites": (
                _prerequisite_links(
                    course.soft_prerequisite,
                    course_lookup,
                )
            ),
        },
    )


def download_resource_file(
    request,
    resource_id,
    file_kind,
):
    """Stream an uploaded resource as a real download."""
    resource = get_object_or_404(
        _public_resources(Resource.objects.all()),
        id=resource_id,
    )

    if file_kind == "resource":
        stored_file = resource.file
    elif file_kind == "solution":
        stored_file = resource.solution_file
    else:
        raise Http404(
            "Unknown resource file type."
        )

    if not stored_file:
        raise Http404(
            "This resource has no uploaded file."
        )

    filename = (
        Path(stored_file.name).name
        or "studybee-download"
    )

    try:
        file_handle = stored_file.open("rb")
    except (
        FileNotFoundError,
        OSError,
        ValueError,
    ) as exc:
        raise Http404(
            "The requested file could not be opened."
        ) from exc

    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=filename,
    )


def get_safe_next_url(request):
    next_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or reverse("home")
    )

    is_safe = url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )

    if is_safe:
        return next_url

    return reverse("home")


def get_back_label(next_url):
    if next_url in {
        reverse("home"),
        "/",
    }:
        return "← Back to home"

    return "← Back to previous page"


def report_issue(request):
    next_url = get_safe_next_url(request)
    resource_id = (
        request.POST.get("resource")
        or request.GET.get("resource")
    )
    linked_resource = None

    if resource_id and str(resource_id).isdigit():
        linked_resource = Resource.objects.filter(
            pk=int(resource_id)
        ).select_related("course").first()

    report_user = (
        request.user
        if student_is_verified(request.user) and request.user.email
        else None
    )

    initial = {}
    if linked_resource:
        initial.update(
            {
                "resource": linked_resource,
                "course_code": linked_resource.course.course_code,
                "resource_title_or_link": linked_resource.title,
                "issue_type": "BROKEN_LINK",
            }
        )
    if report_user and report_user.email:
        initial["contact_email"] = report_user.email

    if request.method == "POST":
        form = ReportIssueForm(
            request.POST,
            initial=initial,
            user=report_user,
        )

        if form.is_valid():
            report = form.save(commit=False)
            if report_user:
                report.reporter = report_user
                report.contact_email = report_user.email
            report.save()

            if report.resource:
                Resource.objects.filter(pk=report.resource_id).update(
                    verification_status="NEEDS_REVIEW",
                    verified_by=None,
                    verified_at=None,
                )

            request.session["reported_issue_reference"] = report.reference_code
            if report_user:
                send_report_received_email(report.pk)

            if _wants_json(request):
                return JsonResponse(
                    {
                        "ok": True,
                        "reference": report.reference_code,
                    }
                )

            return redirect(
                f"{reverse('report_success')}?{urlencode({'next': next_url})}"
            )

        if _wants_json(request):
            return JsonResponse(
                {
                    "ok": False,
                    "errors": _form_error_payload(form),
                },
                status=400,
            )
    else:
        form = ReportIssueForm(initial=initial, user=report_user)

    return render(
        request,
        "resources/report_issue.html",
        {
            "form": form,
            "next_url": next_url,
            "back_label": get_back_label(next_url),
            "linked_resource": linked_resource,
            "report_user": report_user,
        },
    )


def report_success(request):
    next_url = get_safe_next_url(request)
    reference = request.session.pop("reported_issue_reference", "")

    return render(
        request,
        "resources/report_success.html",
        {
            "next_url": next_url,
            "back_label": get_back_label(next_url),
            "reference_code": reference,
        },
    )


@verified_student_required
def submit_resource(request):
    if request.method == "POST":
        form = ResourceSubmissionForm(request.POST, request.FILES)

        if form.is_valid():
            submission = form.save(commit=False)
            submission.submitted_by = request.user
            submission.submitter_email = request.user.email
            submission.submitter_name = student_name_from_email(
                request.user.email
            )
            submission.save()
            request.session["submitted_resource_title"] = submission.title
            request.session["submitted_resource_reference"] = (
                submission.reference_code
            )
            send_submission_received_email(submission.pk)
            return redirect("submit_resource_success")
    else:
        form = ResourceSubmissionForm()

    return render(
        request,
        "resources/submit_resource.html",
        {
            "form": form,
            "student_email": request.user.email,
            "student_name": student_name_from_email(
                request.user.email
            ),
        },
    )


@verified_student_required
def submit_resource_success(request):
    title = request.session.pop("submitted_resource_title", "")
    reference = request.session.pop("submitted_resource_reference", "")

    return render(
        request,
        "resources/submit_resource_success.html",
        {
            "submitted_title": title,
            "reference_code": reference,
        },
    )


def _safe_destination(request, value, fallback="home"):
    candidate = (value or "").strip()
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return reverse(fallback)


def _auth_redirect(request, mode="login", next_url=""):
    destination = _safe_destination(request, next_url)
    params = urlencode({"auth": mode, "next": destination})
    return redirect(f"{reverse('home')}?{params}")


def _verified_user_for_email(email):
    profile = StudentProfile.objects.select_related("user").filter(
        verified_email__iexact=email,
    ).first()
    if profile and student_is_verified(profile.user):
        return profile.user
    return None


def _user_for_email(email):
    return get_user_model().objects.filter(
        email__iexact=email,
    ).order_by("id").first()


def _otp_request_limit_reached(*, email, request_ip):
    since = timezone.now() - timedelta(hours=1)
    email_count = EmailVerificationCode.objects.filter(
        email=email,
        created_at__gte=since,
    ).count()
    ip_count = (
        EmailVerificationCode.objects.filter(
            request_ip=request_ip,
            created_at__gte=since,
        ).count()
        if request_ip
        else 0
    )
    return bool(
        email_count >= settings.STUDENT_OTP_MAX_REQUESTS_PER_HOUR
        or (
            request_ip
            and ip_count
            >= settings.STUDENT_OTP_MAX_REQUESTS_PER_IP_PER_HOUR
        )
    )


def _send_verification_code(*, email, purpose, request_ip):
    otp, code = EmailVerificationCode.issue(
        email=email,
        purpose=purpose,
        request_ip=request_ip,
        lifetime_minutes=settings.STUDENT_OTP_LIFETIME_MINUTES,
    )
    try:
        send_account_code_email(
            email=email,
            code=code,
            lifetime_minutes=settings.STUDENT_OTP_LIFETIME_MINUTES,
            purpose=purpose,
        )
    except Exception:
        otp.delete()
        raise
    return otp


def _latest_usable_code(*, email, purpose):
    return EmailVerificationCode.objects.filter(
        email=email,
        purpose=purpose,
        used_at__isnull=True,
    ).order_by("-created_at").first()


def _validate_code(form, *, email, purpose):
    otp = _latest_usable_code(email=email, purpose=purpose)
    if not otp or not otp.is_usable:
        form.add_error(
            "code",
            "This code expired or can no longer be used. Request a new one.",
        )
        return None
    if not otp.matches(form.cleaned_data["code"]):
        EmailVerificationCode.objects.filter(pk=otp.pk).update(
            attempts=F("attempts") + 1
        )
        form.add_error("code", "That code is not correct.")
        return None
    return otp


def _finish_student_login(request, user, *, remember_me=True):
    login(
        request,
        user,
        backend="django.contrib.auth.backends.ModelBackend",
    )
    if remember_me:
        request.session.set_expiry(settings.SESSION_COOKIE_AGE)
    else:
        request.session.set_expiry(0)


@never_cache
@sensitive_post_parameters("password")
def student_login(request):
    wants_json = _wants_json(request)
    next_url = _safe_destination(
        request,
        request.POST.get("next") or request.GET.get("next"),
    )

    if request.method != "POST":
        if student_is_verified(request.user):
            return redirect("student_account")
        return _auth_redirect(request, "login", next_url)

    if request.user.is_authenticated:
        logout(request)

    form = StudentLoginForm(request.POST)
    if form.is_valid():
        email = form.cleaned_data["email"]
        existing_user = _verified_user_for_email(email)
        authenticated_user = None
        if existing_user and existing_user.has_usable_password():
            authenticated_user = authenticate(
                request,
                username=existing_user.get_username(),
                password=form.cleaned_data["password"],
            )

        if authenticated_user is None:
            form.add_error(
                None,
                "The email or password is incorrect. Sign up first or reset your password.",
            )
        else:
            _finish_student_login(
                request,
                authenticated_user,
                remember_me=form.cleaned_data["remember_me"],
            )
            messages.success(request, "You are now logged in to StudyBee.")
            if wants_json:
                return JsonResponse({"ok": True, "redirect": next_url})
            return redirect(next_url)

    if wants_json:
        return JsonResponse(
            {"ok": False, "errors": _form_error_payload(form)},
            status=400,
        )
    messages.error(request, "Please correct the login details and try again.")
    return _auth_redirect(request, "login", next_url)


@never_cache
def student_signup_request(request):
    wants_json = _wants_json(request)
    next_url = _safe_destination(
        request,
        request.POST.get("next") or request.GET.get("next"),
    )

    if request.method != "POST":
        return _auth_redirect(request, "signup", next_url)

    if request.user.is_authenticated:
        logout(request)

    form = StudentEmailForm(request.POST)
    if form.is_valid():
        email = form.cleaned_data["email"]
        existing_user = _verified_user_for_email(email)
        if existing_user and existing_user.has_usable_password():
            form.add_error(
                "email",
                "A StudyBee account already exists for this email. Log in instead.",
            )
        else:
            request_ip = client_ip(request)
            if _otp_request_limit_reached(email=email, request_ip=request_ip):
                form.add_error(
                    "email",
                    "Too many codes were requested. Wait before trying again.",
                )
            else:
                try:
                    _send_verification_code(
                        email=email,
                        purpose="SIGNUP",
                        request_ip=request_ip,
                    )
                except Exception:
                    form.add_error(
                        None,
                        "The sign-up code could not be sent. Please try again shortly.",
                    )
                else:
                    request.session["student_signup_email"] = email
                    request.session["student_signup_next"] = next_url
                    if wants_json:
                        return JsonResponse(
                            {
                                "ok": True,
                                "email": email,
                                "lifetime_minutes": settings.STUDENT_OTP_LIFETIME_MINUTES,
                            }
                        )
                    messages.success(
                        request,
                        "A six-digit sign-up code was sent to your BRACU email.",
                    )
                    return _auth_redirect(request, "signup-complete", next_url)

    if wants_json:
        return JsonResponse(
            {"ok": False, "errors": _form_error_payload(form)},
            status=400,
        )
    messages.error(request, "The sign-up code could not be sent.")
    return _auth_redirect(request, "signup", next_url)


@never_cache
@sensitive_post_parameters("code", "password1", "password2")
def student_signup_complete(request):
    wants_json = _wants_json(request)
    email = request.session.get("student_signup_email", "")
    next_url = _safe_destination(
        request,
        request.session.get("student_signup_next", ""),
        fallback="student_account",
    )

    if request.method != "POST":
        return _auth_redirect(request, "signup-complete", next_url)

    if not email:
        payload = {
            "ok": False,
            "message": "Request a sign-up code first.",
        }
        if wants_json:
            return JsonResponse(payload, status=400)
        messages.info(request, payload["message"])
        return _auth_redirect(request, "signup", next_url)

    form = StudentCodePasswordForm(request.POST)
    if form.is_valid():
        otp = _validate_code(form, email=email, purpose="SIGNUP")
        if otp:
            user = _user_for_email(email)
            if user and user.is_staff:
                form.add_error(
                    None,
                    "This email is connected to a staff account and cannot be registered here.",
                )
            else:
                User = get_user_model()
                if user is None:
                    digest = hashlib.sha256(email.encode("utf-8")).hexdigest()[:24]
                    username = f"student_{digest}"
                    user, _created = User.objects.get_or_create(
                        username=username,
                        defaults={"email": email},
                    )
                user.email = email
                user.set_password(form.cleaned_data["password1"])
                user.save(update_fields=["email", "password"])
                StudentProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "display_name": student_name_from_email(email),
                        "verified_email": email,
                        "email_verified_at": timezone.now(),
                    },
                )
                otp.used_at = timezone.now()
                otp.save(update_fields=["used_at"])
                _finish_student_login(request, user, remember_me=True)
                request.session.pop("student_signup_email", None)
                request.session.pop("student_signup_next", None)
                messages.success(request, "Your StudyBee account is ready.")
                if wants_json:
                    return JsonResponse({"ok": True, "redirect": next_url})
                return redirect(next_url)

    if wants_json:
        return JsonResponse(
            {"ok": False, "errors": _form_error_payload(form)},
            status=400,
        )
    messages.error(request, "The account could not be created.")
    return _auth_redirect(request, "signup-complete", next_url)


@never_cache
def student_password_reset_request(request):
    wants_json = _wants_json(request)
    next_url = _safe_destination(
        request,
        request.POST.get("next") or request.GET.get("next"),
    )

    if request.method != "POST":
        return _auth_redirect(request, "reset", next_url)

    form = StudentEmailForm(request.POST)
    if form.is_valid():
        email = form.cleaned_data["email"]
        user = _verified_user_for_email(email)
        request.session["student_reset_email"] = email
        request.session["student_reset_next"] = next_url

        if user:
            request_ip = client_ip(request)
            if _otp_request_limit_reached(email=email, request_ip=request_ip):
                form.add_error(
                    "email",
                    "Too many codes were requested. Wait before trying again.",
                )
            else:
                try:
                    _send_verification_code(
                        email=email,
                        purpose="PASSWORD_RESET",
                        request_ip=request_ip,
                    )
                except Exception:
                    form.add_error(
                        None,
                        "The reset code could not be sent. Please try again shortly.",
                    )

        if not form.errors:
            message = (
                "If a StudyBee account exists for this email, a password reset code has been sent."
            )
            if wants_json:
                return JsonResponse(
                    {
                        "ok": True,
                        "email": email,
                        "message": message,
                        "lifetime_minutes": settings.STUDENT_OTP_LIFETIME_MINUTES,
                    }
                )
            messages.success(request, message)
            return _auth_redirect(request, "reset-complete", next_url)

    if wants_json:
        return JsonResponse(
            {"ok": False, "errors": _form_error_payload(form)},
            status=400,
        )
    messages.error(request, "The reset request could not be completed.")
    return _auth_redirect(request, "reset", next_url)


@never_cache
@sensitive_post_parameters("code", "password1", "password2")
def student_password_reset_complete(request):
    wants_json = _wants_json(request)
    email = request.session.get("student_reset_email", "")
    next_url = _safe_destination(
        request,
        request.session.get("student_reset_next", ""),
        fallback="student_account",
    )

    if request.method != "POST":
        return _auth_redirect(request, "reset-complete", next_url)

    if not email:
        payload = {
            "ok": False,
            "message": "Request a password reset code first.",
        }
        if wants_json:
            return JsonResponse(payload, status=400)
        messages.info(request, payload["message"])
        return _auth_redirect(request, "reset", next_url)

    form = StudentCodePasswordForm(request.POST)
    if form.is_valid():
        otp = _validate_code(
            form,
            email=email,
            purpose="PASSWORD_RESET",
        )
        user = _verified_user_for_email(email)
        if not user:
            form.add_error(None, "No verified StudyBee account was found.")
        elif otp:
            user.set_password(form.cleaned_data["password1"])
            user.save(update_fields=["password"])
            otp.used_at = timezone.now()
            otp.save(update_fields=["used_at"])
            _finish_student_login(request, user, remember_me=True)
            request.session.pop("student_reset_email", None)
            request.session.pop("student_reset_next", None)
            messages.success(request, "Your password has been reset.")
            if wants_json:
                return JsonResponse({"ok": True, "redirect": next_url})
            return redirect(next_url)

    if wants_json:
        return JsonResponse(
            {"ok": False, "errors": _form_error_payload(form)},
            status=400,
        )
    messages.error(request, "The password could not be reset.")
    return _auth_redirect(request, "reset-complete", next_url)


@never_cache
def student_verify(request):
    """Legacy OTP-login URL retained as a safe redirect."""
    next_url = request.GET.get("next") or request.POST.get("next") or ""
    return _auth_redirect(request, "signup", next_url)


def student_logout(request):
    if request.method == "POST":
        logout(request)
        messages.success(request, "You have been logged out.")
    return redirect("home")


@verified_student_required
def student_account(request):
    submissions = ResourceSubmission.objects.filter(
        submitted_by=request.user
    ).select_related("course", "published_resource")
    reports = ReportIssue.objects.filter(
        reporter=request.user
    ).select_related("resource", "resource__course")

    return render(
        request,
        "resources/student_account.html",
        {
            "submissions": submissions,
            "reports": reports,
            "student_name": student_name_from_email(request.user.email),
            "student_email": request.user.email,
        },
    )


def privacy_policy(request):
    return render(request, "resources/privacy.html")


def terms_of_use(request):
    return render(request, "resources/terms.html")

