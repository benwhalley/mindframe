from django.urls import path
from mindframe.views import create_public_session, SyntheticConversationDetailView


urlpatterns = [
    # Other URLs
    path(
        "start/<str:intervention_slug>/",
        create_public_session,
        name="public_start_session",
    ),
    path(
        "fake/conversation/<int:pk>/",
        SyntheticConversationDetailView.as_view(),
        name="fake_conversation_detail",
    ),
]
