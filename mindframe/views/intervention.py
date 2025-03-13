import logging

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic.base import TemplateView
from django.views.generic import DetailView, ListView, TemplateView
from django.views.generic.edit import FormView

from mindframe.models import Intervention, Step
from mindframe.graphing import mermaid_diagram

logger = logging.getLogger(__name__)


class InterventionListView(LoginRequiredMixin, ListView):
    model = Intervention

    def get_context_data(self, **kwargs):
        ct = super().get_context_data(**kwargs)
        ct["object_list"] = Intervention.objects.all()
        for i in ct["object_list"]:
            i.mermaid = mermaid_diagram(i)
        return ct
