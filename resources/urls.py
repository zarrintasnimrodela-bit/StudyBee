from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),

    path(
        "search/",
        views.global_search,
        name="global_search",
    ),

    # Keep old numeric URLs working.
    # This must come before the slug route because numbers are valid slugs.
    path(
        "course/<int:course_id>/",
        views.legacy_course_detail,
        name="legacy_course_detail",
    ),

    # New clean URL: /course/cse423/
    path(
        "course/<slug:course_code>/",
        views.course_detail,
        name="course_detail",
    ),

    path(
        "resource/<int:resource_id>/download/<str:file_kind>/",
        views.download_resource_file,
        name="download_resource_file",
    ),

    path(
        "submit/",
        views.submit_resource,
        name="submit_resource",
    ),

    path(
        "submit/success/",
        views.submit_resource_success,
        name="submit_resource_success",
    ),

    path(
        "report/",
        views.report_issue,
        name="report_issue",
    ),

    path(
        "report/success/",
        views.report_success,
        name="report_success",
    ),
]