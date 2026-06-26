from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('course/<int:course_id>/', views.course_detail, name='course_detail'),
    path('report/', views.report_issue, name='report_issue'),
    path('report/success/', views.report_success, name='report_success'),
]