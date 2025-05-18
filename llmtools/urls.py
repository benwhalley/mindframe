from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI

from llmtools.api import router as llmtools_router

from .views import JobGroupDetailView, tool_input_view

api = NinjaAPI()
api.add_router("/llmtools/", llmtools_router)

urlpatterns = [
    path("jobgroup/<int:pk>/", JobGroupDetailView.as_view(), name="jobgroup-detail"),
    path("tool/<int:pk>/", tool_input_view, name="tool-input"),
    path("api/", api.urls),
]
