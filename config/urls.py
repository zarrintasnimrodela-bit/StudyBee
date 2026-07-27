from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('resources.urls')),
]

# Django serves local uploads only during local development. In production,
# uploaded files are served directly by Supabase Storage.
if settings.DEBUG and not settings.USE_CLOUD_STORAGE:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
