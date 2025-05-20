from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("mindframe.urls")),
    path("", include("llmtools.urls")),
    # path("auth/", include("magiclink.urls", namespace="magiclink")),
    path("hijack/", include("hijack.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("__debug__/", include("debug_toolbar.urls")),
    path("admin/", admin.site.urls),
    path("actionable/", include("actionable.urls")),
]
