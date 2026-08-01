from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.global_search, name="global_search"),
    path(
        "course/<int:course_id>/",
        views.legacy_course_detail,
        name="legacy_course_detail",
    ),
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
    path("submit/", views.submit_resource, name="submit_resource"),
    path(
        "submit/success/",
        views.submit_resource_success,
        name="submit_resource_success",
    ),
    path("report/", views.report_issue, name="report_issue"),
    path("report/success/", views.report_success, name="report_success"),
    path("account/login/", views.student_login, name="student_login"),
    path(
        "account/signup/",
        views.student_signup_request,
        name="student_signup_request",
    ),
    path(
        "account/signup/complete/",
        views.student_signup_complete,
        name="student_signup_complete",
    ),
    path(
        "account/password-reset/",
        views.student_password_reset_request,
        name="student_password_reset_request",
    ),
    path(
        "account/password-reset/complete/",
        views.student_password_reset_complete,
        name="student_password_reset_complete",
    ),
    path("account/verify/", views.student_verify, name="student_verify"),
    path("account/logout/", views.student_logout, name="student_logout"),
    path("account/", views.student_account, name="student_account"),
    path("privacy/", views.privacy_policy, name="privacy_policy"),
    path("terms/", views.terms_of_use, name="terms_of_use"),
]
