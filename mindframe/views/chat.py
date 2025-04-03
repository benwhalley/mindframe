from django import forms
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, FormView

from mindframe.conversation import listen, respond
from mindframe.models import Conversation, Turn
from mindframe.tree import conversation_history


class ChatReplyForm(forms.Form):
    message = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Type your message..."}))


class ChatReplyView(FormView):
    form_class = ChatReplyForm
    template_name = "chat_reply.html"

    def form_valid(self, form):
        conversation = get_object_or_404(Conversation, uuid=self.kwargs["uuid"])
        t = conversation.turns.all().last()

        nt = listen(t, form.cleaned_data["message"], speaker=self.request.user)
        bt = respond(nt)

        # render form and respond
        return render(
            self.request, self.template_name, {"form": form, "conversation": conversation}
        )

    def form_invalid(self, form):
        return HttpResponse('<div class="message error">Invalid message</div>', status=400)


class TurnDetailView(DetailView):
    model = Turn
    template_name = "chat_turn.html"
    context_object_name = "message"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class NewMessagesView(DetailView):
    model = Turn
    template_name = "chat_new_messages.html"
    slug_field = "uuid"
    slug_url_kwarg = "since_uuid"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get new messages after the given timestamp
        conversation = self.object.conversation
        new_messages = (
            conversation_history(self.object, to_leaf=True)
            .order_by("timestamp")
            .filter(depth__gt=self.object.depth)
        )

        context["new_messages"] = new_messages
        return context


class ChatDetailView(DetailView):
    model = Conversation
    template_name = "chat.html"
    context_object_name = "conversation"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["history"] = conversation_history(self.object.turns.all().last()).order_by(
            "timestamp"
        )
        return context

    @method_decorator(csrf_exempt)
    def post(self, request, *args, **kwargs):
        conversation = self.get_object()
        message_text = request.POST.get("message", "").strip()
        if message_text:
            Turn.objects.create(
                conversation=conversation, sender="user", text=message_text, timestamp=now()
            )
            # Simulate bot response
            Turn.objects.create(
                conversation=conversation,
                sender="bot",
                text=f"Echo: {message_text}",
                timestamp=now(),
            )
            return HttpResponse(
                f'<div class="message user">{message_text}</div>'
                f'<div class="message bot">Echo: {message_text}</div>'
            )
        return HttpResponse("")
