from collections import defaultdict

from django.db.models.functions import Lower
from django.db.models import Count, Q, Case, When, IntegerField
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import ReportIssueForm
from .models import Course, Resource


def home(request):
    query = request.GET.get('q', '')

    courses = Course.objects.annotate(resource_count=Count('resources')).order_by('course_code')

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

    resources = resources.order_by('title')

    resources = resources.order_by(Lower('title'))

    grouped_dict = defaultdict(list)

    for resource in resources:
        grouped_dict[resource.get_category_display()].append(resource)

    grouped_resources = sorted(grouped_dict.items(), key=lambda item: item[0])

    return render(request, 'resources/course_detail.html', {
        'course': course,
        'resources': resources,
        'grouped_resources': grouped_resources,
        'all_resources_count': all_resources_count,
        'exam_part': exam_part,
        'category': category,
        'question_type': question_type,
        'search_query': search_query,
    })


def get_safe_next_url(request):
    next_url = request.POST.get('next') or request.GET.get('next') or reverse('home')

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
            return redirect(f"{reverse('report_success')}?next={next_url}")
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