import logging

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, ListView, TemplateView
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView

from mindframe.graphing import mermaid_diagram
from mindframe.models import Intervention, Step

logger = logging.getLogger(__name__)


class StepDetailView(PermissionRequiredMixin, LoginRequiredMixin, DetailView):

    permission_required = "mindframe.view_intervention"
    model = Step

    def get_context_data(self, **kwargs):
        ct = super().get_context_data(**kwargs)
        ct["object"].mermaid = mermaid_diagram(ct["object"].intervention, highlight=ct["object"])
        return ct


class InterventionListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    permission_required = "mindframe.view_intervention"
    model = Intervention

    def get_context_data(self, **kwargs):
        ct = super().get_context_data(**kwargs)
        ct["object_list"] = Intervention.objects.all()
        for i in ct["object_list"]:
            i.mermaid = mermaid_diagram(i)
        return ct
