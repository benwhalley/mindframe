import pickle
from copy import deepcopy

from decouple import config
from django.http import HttpResponse
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt

import mindframe.views.conversation as cv
import mindframe.views.general as gv
import mindframe.views.hyde as hv
import mindframe.views.intervention as iv
from mindframe.telegram import TelegramBotClient


def pickle_minimal_request(request):
    minimal_data = {
        "path": request.path,
        "method": request.method,
        "GET": dict(request.GET),
        "POST": dict(request.POST),
        "META": dict(request.META),
        "headers": dict(request.headers),
        "session": dict(request.session),
        "body": request.body,
    }
    return pickle.dumps(minimal_data)


@csrf_exempt
def telegram_webhook(request):
    """
    Django view function for handling Telegram webhook requests.
    This function delegates processing to the BotController.
    """
    # capture the last request so we can capture requests and use for testing
    # try:
    #     with open("request.pickle", "wb") as f:
    #         print(pickle_minimal_request(request))
    #         f.write(pickle_minimal_request(request))

    # except Exception as e:
    #     print(f"Error serializing request data: {e}")

    tgmb = TelegramBotClient(
        bot_name=config("TELEGRAM_BOT_NAME", "MindframerBot"),
        bot_secret_token=config("TELEGRAM_BOT_TOKEN", None),
        webhook_url=config("TELEGRAM_WEBHOOK_URL", None),
        webhook_validation_token=config("TELEGRAM_WEBHOOK_VALIDATION_TOKEN", None),
    )

    return tgmb.process_webhook(request)


urlpatterns = [
    path("chat/", include("mindframe.chat_urls")),
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
