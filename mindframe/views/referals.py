import json
import logging
from typing import Tuple

from decouple import config
from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
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
    UsagePlan,
    UserReferal,
)

logger = logging.getLogger(__name__)


def make_referal_using_plan(
    plan, user, data=None, intervention=None, bot_interface=None
) -> Tuple[UserReferal, Conversation]:

    if (intervention and bot_interface) or (not intervention and not bot_interface):
        raise Exception("Must provide either intervention or bot_interface (but not both)")

    if not intervention:
        intervention = bot_interface.intervention

    # if the permitted_interventions field is empty, don't check anything
    if plan.permitted_interventions.all().count() > 0:
        if intervention not in plan.permitted_interventions.all():
            raise Exception("Intervention not permitted for this token")

    # Create conversation

    referal = UserReferal.objects.create(usage_plan=plan)

    conversation = Conversation.objects.create(user_referal=referal, bot_interface=bot_interface)

    bot_turn = initialise_new_conversation(conversation, intervention, user)

    # Create note with referal data and UserReferal
    note = Note.objects.create(
        # must be on the therapist's turn so notes are available to the therapist later
        turn=conversation.turns.exclude(speaker=user).first(),
        judgement=None,  # No judgement for referal data
        data=data or {"data_source": "UserReferal"},
    )

    referal.note = note
    referal.save()

    return referal, conversation


class ReferalForm(forms.Form):
    usage_plan = forms.ModelChoiceField(queryset=UsagePlan.objects.none())
    bot_interface = forms.ModelChoiceField(
        queryset=BotInterface.objects.none(),
        required=False,
    )
    intervention = forms.ModelChoiceField(queryset=Intervention.objects.none(), required=False)
    username = forms.CharField(
        required=True, initial="AnonymousUser", help_text="A username for this participant."
    )
    create_if_doesnt_exist = forms.BooleanField(
        required=False,
        initial=True,
        help_text="If this is checked, a new user will be created if one matching the username doesn't already exist.",
    )

    data = forms.JSONField(
        required=False,
        initial={"nickname": "..."},
    )
    redirect = forms.ChoiceField(
        choices=[("web", "Web"), ("telegram", "Telegram"), ("json", "JSON")], initial="web"
    )

    def clean(self):
        cd = super().clean()

        if not cd.get("intervention", None) and not cd.get("bot_interface", None):
            raise ValidationError(f"You must either specify a bot or an intervention")
        return cd

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Safe to query now
        self.fields["usage_plan"].queryset = UsagePlan.objects.all()
        self.fields["intervention"].queryset = Intervention.objects.all()
        self.fields["bot_interface"].queryset = BotInterface.objects.all()

        # firstplan = UsagePlan.objects.filter(label__istartswith="default").first()
        # if firstplan:
        #     self.fields["usage_plan"].initial = firstplan

        # pick = Intervention.objects.filter(slug__istartswith="demo").first()
        # if pick:
        #     self.fields["intervention"].initial = pick


@method_decorator(csrf_exempt, name="dispatch")
class CreateReferalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to handle creation of new referals from external sources"""

    permission_required = "mindframe.add_userreferal"

    def get(self, request):
        form = ReferalForm()
        return render(request, "referal_form.html", {"form": form})

    def post(self, request):
        try:
            form = ReferalForm(request.POST)
            try:
                valid = form.is_valid()
                data = form.cleaned_data
                redirect = data.get("redirect", "web")

                if not valid:
                    if redirect == "json":
                        return JsonResponse({"error": form.errors}, status=400)
                    else:
                        return render(request, "referal_form.html", {"form": form})

                create_if_doesnt_exist = data.get("create_if_doesnt_exist", False)

                if create_if_doesnt_exist:
                    user, _ = CustomUser.objects.get_or_create(
                        username=data.get("username"), role="client"
                    )
                else:
                    user = CustomUser.objects.get(username=data["username"])

                # plan, username, data=None, intervention_slug=None, bot_interface=None
                user_referal, conversation = make_referal_using_plan(
                    plan=data["usage_plan"],
                    user=user,
                    data=data["data"],
                    intervention=data["intervention"],
                    bot_interface=data["bot_interface"],
                )

            except Exception as e:
                raise e
                return JsonResponse({"error": str(e)}, status=400)

            web_url = request.build_absolute_uri(
                reverse("conversation_detail", args=[conversation.turns.all().last().uuid])
            )

            telegram_link = conversation.external_chat_link()

            if redirect == "telegram":
                return HttpResponseRedirect(telegram_link)

            if redirect == "json":
                return JsonResponse(
                    {
                        "referal": str(user_referal.uuid),
                        "conversation_id": str(conversation.uuid),
                        "url": web_url,
                        "telegram_link": telegram_link,
                    }
                )
            return HttpResponseRedirect(reverse("referal_detail", args=[user_referal.uuid]))

        except Exception as e:
            raise e
            logger.warning("PROBLEMN: ", str(e))


class ReferalDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):

    permission_required = "mindframe.add_userreferal"
    model = UserReferal
    template_name = "referal_detail.html"

    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     context["referal"] = self.object
    #     return context
