from django.urls import path


from mindframe.views.general import start_gradio_chat, IndexView

from mindframe.views.hyde import (
    RAGHyDEComparisonView,
)
from mindframe.views.conversation import (
    ConversationDetailView,
    ImportConversationView,
    ConversationMermaidView,
)

from mindframe.telegram import telegram_webhook

urlpatterns = [
    path("telegram-webhook/", telegram_webhook, name="telegram_webhook"),
    # Other URLs
    path(
        "start/from-turn/<str:turn_uuid>/",
        start_gradio_chat,
        name="start_gradio_chat_from_turn",
    ),
    path(
        "start/<str:intervention_slug>/",
        start_gradio_chat,
        name="start_gradio_chat",
    ),
    path(
        "import/fake/",
        ImportConversationView.as_view(),
        name="import_conversation",
    ),
    path(
        "conversations/<str:uuid>/",
        ConversationDetailView.as_view(),
        name="conversation_detail",
    ),
    path(
        "conversations/<str:uuid>/",
        ConversationDetailView.as_view(to_leaf=True),
        name="conversation_detail_to_leaf",
    ),
    path(
        "conversation/mermaid/<str:uuid>/",
        ConversationMermaidView.as_view(),
        name="conversation_mermaid",
    ),
    path("rag-test/", RAGHyDEComparisonView.as_view(), name="rag_test"),
    path("", IndexView.as_view(), name="index"),  # Index page
]
