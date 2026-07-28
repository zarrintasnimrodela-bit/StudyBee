from collections import defaultdict
from pathlib import Path

from django.db.models.functions import Lower
from django.db.models import Case, Count, IntegerField, Q, When
from django.http import FileResponse, Http404
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import ReportIssueForm
from .models import Course, Resource


def home(request):
    query = request.GET.get('q', '')

    courses = Course.objects.annotate(
        resource_count=Count('resources')
    ).order_by('course_code')

    if query:
        courses = courses.filter(
            Q(course_code__icontains=query) |
            Q(course_title__icontains=query)
        )

    total_courses = Course.objects.count()
    total_resources = Resource.objects.count()
    latest_resource = Resource.objects.order_by('-uploaded_at').first()

    return render(request, 'resources/home.html', {
        'courses': courses,
        'query': query,
        'total_courses': total_courses,
        'total_resources': total_resources,
        'latest_resource': latest_resource,
    })


def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    all_resources_count = course.resources.count()

    exam_part = request.GET.get('exam_part', '')
    category = request.GET.get('category', '')
    question_type = request.GET.get('question_type', '')
    search_query = request.GET.get('q', '')

    resources = course.resources.all()

    if exam_part:
        resources = resources.filter(exam_part=exam_part)

    if category:
        resources = resources.filter(category=category)

    if question_type:
        resources = resources.filter(question_type=question_type)

    if search_query:
        resources = resources.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    alphabetical_categories = sorted(
        Resource.CATEGORY_CHOICES,
        key=lambda choice: choice[1].lower(),
    )

    category_order = Case(
        *[
            When(category=category_code, then=position)
            for position, (category_code, _label)
            in enumerate(alphabetical_categories)
        ],
        default=len(alphabetical_categories),
        output_field=IntegerField(),
    )

    resources = resources.annotate(
        category_sort=category_order
    ).order_by('category_sort', Lower('title'))

    paginator = Paginator(resources, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    page_resources = list(page_obj.object_list)
    resources_by_category = defaultdict(list)

    for resource in page_resources:
        resources_by_category[resource.category].append(resource)

    previous_category = None
    next_category = None

    if page_obj.has_previous():
        previous_index = page_obj.start_index() - 2
        previous_category = resources.values_list(
            'category',
            flat=True,
        )[previous_index]

    if page_obj.has_next():
        next_index = page_obj.end_index()
        next_category = resources.values_list(
            'category',
            flat=True,
        )[next_index]

    grouped_resources = []

    for category_code, category_label in alphabetical_categories:
        section_resources = resources_by_category.get(category_code)

        if not section_resources:
            continue

        grouped_resources.append({
            'name': category_label,
            'resources': section_resources,
            'continued_from_previous': (
                previous_category == category_code
            ),
            'continues_next': next_category == category_code,
        })

    pagination_params = request.GET.copy()
    pagination_params.pop('page', None)
    pagination_query = pagination_params.urlencode()

    pagination_items = []

    for page_number in paginator.get_elided_page_range(
        page_obj.number,
        on_each_side=1,
        on_ends=1,
    ):
        if page_number == paginator.ELLIPSIS:
            pagination_items.append({
                'ellipsis': True,
            })
        else:
            pagination_items.append({
                'number': page_number,
                'current': page_number == page_obj.number,
            })

    return render(request, 'resources/course_detail.html', {
        'course': course,
        'resources': page_resources,
        'grouped_resources': grouped_resources,
        'page_obj': page_obj,
        'pagination_items': pagination_items,
        'pagination_query': pagination_query,
        'remaining_resources': (
            paginator.count - page_obj.end_index()
        ),
        'all_resources_count': all_resources_count,
        'exam_part': exam_part,
        'category': category,
        'question_type': question_type,
        'search_query': search_query,
    })


def download_resource_file(request, resource_id, file_kind):
    """Stream an uploaded resource as a real browser download."""
    resource = get_object_or_404(Resource, id=resource_id)

    if file_kind == 'resource':
        stored_file = resource.file
    elif file_kind == 'solution':
        stored_file = resource.solution_file
    else:
        raise Http404("Unknown resource file type.")

    if not stored_file:
        raise Http404("This resource has no uploaded file.")

    filename = Path(stored_file.name).name or 'studybee-download'

    try:
        file_handle = stored_file.open('rb')
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise Http404("The requested file could not be opened.") from exc

    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=filename,
    )


def get_safe_next_url(request):
    next_url = (
        request.POST.get('next')
        or request.GET.get('next')
        or reverse('home')
    )

    is_safe = url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure()
    )

    if is_safe:
        return next_url

    return reverse('home')


def get_back_label(next_url):
    if next_url == reverse('home') or next_url == '/':
        return '← Back to home'

    return '← Back to previous page'


def report_issue(request):
    next_url = get_safe_next_url(request)

    if request.method == 'POST':
        form = ReportIssueForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect(
                f"{reverse('report_success')}?next={next_url}"
            )
    else:
        form = ReportIssueForm()

    return render(request, 'resources/report_issue.html', {
        'form': form,
        'next_url': next_url,
        'back_label': get_back_label(next_url),
    })


def report_success(request):
    next_url = get_safe_next_url(request)

    return render(request, 'resources/report_success.html', {
        'next_url': next_url,
        'back_label': get_back_label(next_url),
    })
