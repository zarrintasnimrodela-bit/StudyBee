from django.urls import path

from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path(
        'course/<int:course_id>/',
        views.course_detail,
        name='course_detail',
    ),
    path(
        'resource/<int:resource_id>/download/<str:file_kind>/',
        views.download_resource_file,
        name='download_resource_file',
    ),
    path('report/', views.report_issue, name='report_issue'),
    path(
        'report/success/',
        views.report_success,
        name='report_success',
    ),
]
