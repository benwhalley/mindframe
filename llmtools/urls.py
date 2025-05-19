from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI

from llmtools.api import router as llmtools_router

from .views import JobGroupDetailView, ToolListView, tool_input_view

api = NinjaAPI()
api.add_router("/llmtools/", llmtools_router)

urlpatterns = [
    path("tools/", ToolListView.as_view(), name="tool_list"),
    path("jobgroup/<int:pk>/", JobGroupDetailView.as_view(), name="jobgroup-detail"),
    path("tool/<int:pk>/", tool_input_view, name="tool_input"),
    path("api/", api.urls),
]
