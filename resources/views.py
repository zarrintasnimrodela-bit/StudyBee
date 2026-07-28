import re
from collections import defaultdict
from pathlib import Path

from django.core.paginator import Paginator
from django.db.models import Case, Count, IntegerField, Q, When
from django.db.models.functions import Lower
from django.http import FileResponse, Http404
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse
from django.utils.http import (
    url_has_allowed_host_and_scheme,
)

from .forms import (
    ReportIssueForm,
    ResourceSubmissionForm,
)
from .models import (
    Course,
    ReportIssue,
    Resource,
    SEMESTER_TERM_CHOICES,
)


PUBLIC_RESOURCE_STATUSES = (
    "UNVERIFIED",
    "VERIFIED",
)


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


def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    all_resources_count = _public_resources(
        course.resources.all()
    ).count()

    exam_part = request.GET.get("exam_part", "")
    category = request.GET.get("category", "")
    question_type = request.GET.get(
        "question_type",
        "",
    )
    semester_term = request.GET.get(
        "semester_term",
        "",
    )
    semester_year = request.GET.get(
        "semester_year",
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

        if semester_term:
            resources = resources.filter(
                semester_term=semester_term
            )

        if semester_year.isdigit():
            resources = resources.filter(
                semester_year=int(semester_year)
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

    available_years = (
        _public_resources(course.resources.all()).exclude(
            semester_year__isnull=True
        )
        .values_list("semester_year", flat=True)
        .distinct()
        .order_by("-semester_year")
    )

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
            "semester_term": semester_term,
            "semester_year": semester_year,
            "search_query": search_query,
            "focus_resource": focus_resource,
            "semester_term_choices": (
                SEMESTER_TERM_CHOICES
            ),
            "available_years": available_years,
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

    initial = {}

    if linked_resource:
        initial = {
            "resource": linked_resource,
            "course_code": (
                linked_resource.course.course_code
            ),
            "resource_title_or_link": (
                linked_resource.title
            ),
            "issue_type": "BROKEN_LINK",
        }

    if request.method == "POST":
        form = ReportIssueForm(
            request.POST,
            initial=initial,
        )

        if form.is_valid():
            report = form.save()

            if report.resource:
                Resource.objects.filter(
                    pk=report.resource_id
                ).update(
                    verification_status="NEEDS_REVIEW",
                    verified_by=None,
                    verified_at=None,
                )

            return redirect(
                (
                    f"{reverse('report_success')}"
                    f"?next={next_url}"
                )
            )
    else:
        form = ReportIssueForm(initial=initial)

    return render(
        request,
        "resources/report_issue.html",
        {
            "form": form,
            "next_url": next_url,
            "back_label": get_back_label(
                next_url
            ),
            "linked_resource": linked_resource,
        },
    )


def report_success(request):
    next_url = get_safe_next_url(request)

    return render(
        request,
        "resources/report_success.html",
        {
            "next_url": next_url,
            "back_label": get_back_label(
                next_url
            ),
        },
    )


def submit_resource(request):
    if request.method == "POST":
        form = ResourceSubmissionForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            submission = form.save()
            request.session[
                "submitted_resource_title"
            ] = submission.title
            return redirect("submit_resource_success")
    else:
        form = ResourceSubmissionForm()

    return render(
        request,
        "resources/submit_resource.html",
        {"form": form},
    )


def submit_resource_success(request):
    title = request.session.pop(
        "submitted_resource_title",
        "",
    )

    return render(
        request,
        "resources/submit_resource_success.html",
        {"submitted_title": title},
    )
