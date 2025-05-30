from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI

from llmtools.api import router as llmtools_router

from .views import JobGroupDetailView, ToolListView, download_excel, tool_input_view

api = NinjaAPI()
api.add_router("/llmtools/", llmtools_router)

urlpatterns = [
    path("tools/", ToolListView.as_view(), name="tool_list"),
    path("jobgroup/<int:pk>/", JobGroupDetailView.as_view(), name="jobgroup-detail"),
    path("jobgroup/data/<str:uuid>/", download_excel, name="jobgroup_excel"),
    path("tool/<int:pk>/", tool_input_view, name="tool_input"),
    path("api/", api.urls),
]
