import json
import logging

from decouple import config
from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, FormView

from mindframe.conversation import initialise_new_conversation
from mindframe.models import (
    BotInterface,
    Conversation,
    CustomUser,
    Intervention,
    Note,
    Referal,
    ReferalToken,
)

logger = logging.getLogger(__name__)


def make_referal_using_token(token, intervention_slug, username, data=None, bot_interface=None):

    user = get_object_or_404(CustomUser, username=username)

    # Get and validate token
    referaltoken = get_object_or_404(ReferalToken, token=token)

    # Get and validate intervention
    intervention = get_object_or_404(Intervention, slug=intervention_slug)

    # if the permitted_interventions field is empty, don't check anything
    if referaltoken.permitted_interventions.all().count() > 0:
        if intervention not in referaltoken.permitted_interventions.all():
            raise Exception("Intervention not permitted for this token")

    # Validate username
    if not referaltoken.user_valid(user):
        raise Exception("Invalid username for token")

    # Create conversation
    conversation = Conversation.objects.create()
    bot_turn = initialise_new_conversation(conversation, intervention, user)

    # add bot interface
    conversation.bot_interface = bot_interface
    conversation.save()

    # Create note with referal data
    if not data:
        data = {"conversation_source": "Referal Token"}

    note = Note.objects.create(
        # must be on the therapist's turn so notes are available to the therapist later
        turn=conversation.turns.exclude(speaker=user).first(),
        judgement=None,  # No judgement for referal data
        data=data,
    )
    # Create referal
    referal = Referal.objects.create(conversation=conversation, source=referaltoken, note=note)

    return referal


class ReferalForm(forms.Form):
    referal_token = forms.ModelChoiceField(queryset=ReferalToken.objects.none())
    intervention = forms.ModelChoiceField(queryset=Intervention.objects.none())
    username = forms.CharField(required=True, initial="robert")
    bot_interface = forms.ModelChoiceField(queryset=BotInterface.objects.none())
    create_if_doesnt_exist = forms.BooleanField(required=False, initial=True)
    data = forms.JSONField(
        required=False,
        initial={
            "nickname": "Ben",
            "interests": "climbing, tennis, poetry",
            "current_emotion": "happy",
        },
    )
    redirect = forms.ChoiceField(
        choices=[("web", "Web"), ("telegram", "Telegram"), ("json", "JSON")], initial="web"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Safe to query now
        self.fields["referal_token"].queryset = ReferalToken.objects.all()
        self.fields["intervention"].queryset = Intervention.objects.all()
        self.fields["bot_interface"].queryset = BotInterface.objects.all()

        first_token = ReferalToken.objects.first()
        if first_token:
            self.fields["referal_token"].initial = first_token

        pick = Intervention.objects.filter(slug__istartswith="refer").first()
        if pick:
            self.fields["intervention"].initial = pick


@method_decorator(csrf_exempt, name="dispatch")
class CreateReferalView(LoginRequiredMixin, View):
    """View to handle creation of new referals from external sources"""

    def get(self, request):
        form = ReferalForm()
        return render(request, "referal_form.html", {"form": form})

    def post(self, request):
        try:
            try:
                form = ReferalForm(request.POST)

                if not form.is_valid():
                    return JsonResponse({"error": form.errors}, status=400)

                data = form.cleaned_data
                create_if_doesnt_exist = data.get("create_if_doesnt_exist", False)

                if create_if_doesnt_exist:
                    user, _ = CustomUser.objects.get_or_create(
                        username=data.get("username"), role="client"
                    )

                referal = make_referal_using_token(
                    data["referal_token"].token,
                    data["intervention"].slug,
                    data["username"],
                    data=data["data"],
                    bot_interface=data["bot_interface"],
                )
            except Exception as e:
                return JsonResponse({"error": str(e)}, status=400)

            web_url = request.build_absolute_uri(
                reverse("conversation_detail", args=[referal.conversation.turns.all().last().uuid])
            )

            redirect = data.get("redirect", "web")

            telegram_link = referal.external_chat_link()

            if redirect == "telegram":
                return HttpResponseRedirect(telegram_link)

            if redirect == "json":
                return JsonResponse(
                    {
                        "referal": str(referal.uuid),
                        "conversation_id": str(referal.conversation.uuid),
                        "url": web_url,
                        "telegram_link": telegram_link,
                    }
                )
            return HttpResponseRedirect(reverse("referal_detail", args=[referal.uuid]))

        except Exception as e:
            logger.warning(str(e))


class ReferalDetailView(LoginRequiredMixin, DetailView):
    model = Referal
    template_name = "referal_detail.html"

    slug_field = "uuid"
    slug_url_kwarg = "uuid"
