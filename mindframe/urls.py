from django.urls import path
from mindframe.views import (
    create_public_session,
    SyntheticConversationDetailView,
    TreatmentSessionDetailView,
    RAGHyDEComparisonView,
    IndexView,
)

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
    path(
        "sessions/<str:uuid>/",
        TreatmentSessionDetailView.as_view(),
        name="treatment_session_detail",
    ),
    path("rag-test/", RAGHyDEComparisonView.as_view(), name="rag_test"),
    path("", IndexView.as_view(), name="index"),  # Index page
]
