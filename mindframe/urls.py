from django.urls import path
from mindframe.views import create_public_session

urlpatterns = [
    # Other URLs
    path(
        "start/<str:intervention_slug>/",
        create_public_session,
        name="public_start_session",
    ),
]
