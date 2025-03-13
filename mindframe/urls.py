from django.urls import path

from mindframe.telegram import telegram_webhook
import mindframe.views.conversation as cv
import mindframe.views.intervention as iv
import mindframe.views.general as gv
import mindframe.views.hyde as hv

urlpatterns = [
    path("interventions/", iv.InterventionListView.as_view(), name="intervention_list"),
    path("steps/<int:pk>/", iv.StepDetailView.as_view(), name="step_detail"),
    path("telegram-webhook/", telegram_webhook, name="telegram_webhook"),
    # Other URLs
    path(
        "start/from-turn/<str:turn_uuid>/",
        gv.start_gradio_chat,
        name="start_gradio_chat_from_turn",
    ),
    path(
        "start/<str:intervention_slug>/",
        gv.start_gradio_chat,
        name="start_gradio_chat",
    ),
    path(
        "import/fake/",
        cv.ImportConversationView.as_view(),
        name="import_conversation",
    ),
    path(
        "conversations/<str:uuid>/",
        cv.ConversationDetailView.as_view(),
        name="conversation_detail",
    ),
    path(
        "conversations/<str:uuid>/transcript/",
        cv.ConversationDetailView.as_view(template_name="conversation_transcript.html"),
        name="conversation_transcript",
    ),
    path(
        "conversations/<str:uuid>/leaf/",
        cv.ConversationDetailView.as_view(to_leaf=True),
        name="conversation_detail_to_leaf",
    ),
    path(
        "conversation/<str:uuid>/mermaid/",
        cv.ConversationMermaidView.as_view(),
        name="conversation_mermaid",
    ),
    path("rag-test/", hv.RAGHyDEComparisonView.as_view(), name="rag_test"),
    path("", gv.IndexView.as_view(), name="index"),  # Index page
]
