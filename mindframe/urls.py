import pickle
from copy import deepcopy

from decouple import config
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView

import mindframe.views.conversation as cv
import mindframe.views.general as gv
import mindframe.views.hyde as hv
import mindframe.views.intervention as iv
import mindframe.views.referals as rv
from mindframe.models import BotInterface


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
def bot_interface(request, pk):

    obj = get_object_or_404(BotInterface, pk=pk)
    return obj.bot_client().process_webhook(request)


urlpatterns = [
    path("chat/", include("mindframe.chat_urls")),
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
    path("abbout", TemplateView.as_view(template_name="about.html"), name="about"),
]
