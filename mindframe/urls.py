from django.urls import path

from mindframe.telegram import telegram_webhook
from mindframe.views.conversation import (
    ConversationDetailView,
    ConversationMermaidView,
    ImportConversationView,
)
from mindframe.views.general import IndexView, start_gradio_chat
from mindframe.views.hyde import RAGHyDEComparisonView

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
        "conversations/<str:uuid>/transcript/",
        ConversationDetailView.as_view(template_name="conversation_transcript.html"),
        name="conversation_transcript",
    ),
    path(
        "conversations/<str:uuid>/leaf/",
        ConversationDetailView.as_view(to_leaf=True),
        name="conversation_detail_to_leaf",
    ),
    path(
        "conversation/<str:uuid>/mermaid/",
        ConversationMermaidView.as_view(),
        name="conversation_mermaid",
    ),
    path("rag-test/", RAGHyDEComparisonView.as_view(), name="rag_test"),
    path("", IndexView.as_view(), name="index"),  # Index page
]
