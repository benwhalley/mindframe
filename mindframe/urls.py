from django.urls import path


from mindframe.views.general import create_public_session, IndexView

from mindframe.views.hyde import (
    RAGHyDEComparisonView,
)
from mindframe.views.conversation import (
    ConversationDetailView,
    ImportConversationView,
)

from mindframe.telegram import telegram_webhook

urlpatterns = [
    path("telegram-webhook/", telegram_webhook, name="telegram_webhook"),
    # Other URLs
    path(
        "start/<str:intervention_slug>/",
        create_public_session,
        name="public_start_session",
    ),
    path(
        "import/fake/",
        ImportConversationView.as_view(),
        name="import_conversation",
    ),
    # path(
    #     "fake/conversation/<int:pk>/",
    #     SyntheticConversationDetailView.as_view(),
    #     name="synthetic_conversation_detail",
    # ),
    path(
        "conversations/<str:uuid>/",
        ConversationDetailView.as_view(),
        name="conversation_detail",
    ),
    path("rag-test/", RAGHyDEComparisonView.as_view(), name="rag_test"),
    path("", IndexView.as_view(), name="index"),  # Index page
]
