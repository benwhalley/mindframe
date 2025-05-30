import logging
import pickle
from copy import deepcopy
from pathlib import Path

from decouple import config
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import include, path
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView

import mindframe.views.conversation as cv
import mindframe.views.general as gv
import mindframe.views.hyde as hv
import mindframe.views.intervention as iv
import mindframe.views.referals as rv
from mindframe.models import BotInterface
from mindframe.settings import SAVE_TELEGRAM_REQUESTS, USE_CELERY_FOR_WEBHOOKS
from mindframe.tasks import process_webhook_async

logger = logging.getLogger(__name__)


# use this for saving telegram requests for playback later
def dump_minimal_request(request):
    try:
        body = request.body.decode("utf-8")
    except UnicodeDecodeError:
        body = "<binary data not UTF-8>"
    minimal_data = {
        "path": request.path,
        "method": request.method,
        "GET": dict(request.GET),
        "POST": dict(request.POST),
        "body": body,
        "headers": dict(request.headers),
        # these cause serialisation issues
        # "META": dict(request.META),
        # "session": dict(request.session),
    }
    return pickle.dumps(minimal_data)


@csrf_exempt
def bot_interface(request, pk):
    obj = get_object_or_404(BotInterface, pk=pk)
    request_data = {
        "method": request.method,
        "headers": dict(request.headers),
        "body": request.body.decode("utf-8"),  # or .hex() if binary data is possible
        "GET": request.GET.dict(),
        "POST": request.POST.dict(),
        # TODO if files are needed add them to the request
    }
    print(request, request.body, pk)

    if USE_CELERY_FOR_WEBHOOKS:
        process_webhook_async(pk, request_data)
    else:
        process_webhook_async.delay(pk, request_data)

    if SAVE_TELEGRAM_REQUESTS:
        timestamp = now().strftime("%Y%m%d-%H%M%S")
        filename = Path(f"telegram_requests/{timestamp}_{pk}.pickle")
        filename.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(filename, "wb") as f:
                f.write(dump_minimal_request(request))
        except Exception as e:
            logger.error(f"Error saving telegram request: {e}")

    return HttpResponse("OK", status=200)


urlpatterns = [
    path("chat/", include("mindframe.chat_urls")),
    path(
        "interventions/<str:slug>/", iv.InterventionDetailView.as_view(), name="intervention_detail"
    ),
    path("interventions/", iv.InterventionListView.as_view(), name="intervention_list"),
    path("steps/<int:pk>/", iv.StepDetailView.as_view(), name="step_detail"),
    path("bot-webhook/<int:pk>", bot_interface, name="bot_webhook"),
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
    path("referal/create/", rv.CreateReferalView.as_view(), name="create_referal"),
    path("referal/<str:uuid>/", rv.ReferalDetailView.as_view(), name="referal_detail"),
    path("", TemplateView.as_view(template_name="index.html"), name="index"),
    path("about/", TemplateView.as_view(template_name="about.html"), name="about"),
]
