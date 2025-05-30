import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from string import Template

import magic


from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.files import File
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView
from langfuse.decorators import langfuse_context

from django import forms
from django.core.exceptions import ValidationError

from llmtools.extract import extract_text

from .models import Job, JobGroup, Tool
from .tasks import run_job

langfuse_context.configure(debug=False)
mime = magic.Magic(mime=True)


@login_required
def download_excel(request, uuid: str):
    jg = get_object_or_404(JobGroup, uuid=uuid)
    buffer = jg.xlsx()

    response = HttpResponse(
        buffer, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="output.xlsx"'
    return response


class ToolInputForm(forms.Form):
    def __init__(self, *args, tool=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"] = forms.FileField(
            label="Upload a single file, or a ZIP file (or enter data below manually)",
            help_text="Upload a single file, or a zip with multiple files to start a batch job",
            required=False,
        )
        self.dynamic_fields = []
        if tool is not None:
            for field_name in tool.get_input_fields():
                self.fields[field_name] = forms.CharField(
                    label=field_name,
                    widget=forms.Textarea(attrs={"rows": 3}),
                    required=False,
                )
                self.dynamic_fields.append(field_name)

    def clean(self):
        cleaned_data = super().clean()
        file_ = cleaned_data.get("file")
        dynamic_filled = [cleaned_data.get(f) for f in self.dynamic_fields if cleaned_data.get(f)]
        if not file_ and len(dynamic_filled) < 1:
            raise ValidationError(
                "You must either upload a file, or fill in at least one of the manual input fields."
            )
        return cleaned_data


class JobGroupDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "llmtools.add_jobgroup"
    model = JobGroup
    template_name = "jobgroup_detail.html"
    context_object_name = "jobgroup"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["jobs"] = self.object.jobs.all()
        context["all_complete"] = not self.object.jobs.filter(completed__isnull=True).exists()
        return context


class ToolListView(PermissionRequiredMixin, ListView):
    permission_required = "llmtools.add_jobgroup"
    model = Tool
    template_name = "tools/tools_list.html"
    context_object_name = "tools"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.request.user.is_authenticated:
            return context

        context["jobgroups"] = JobGroup.objects.filter(owner=self.request.user).order_by("-created")
        return context


def process_file(uploaded_file, job_group):
    ext = os.path.splitext(uploaded_file.name)[1] or ".bin"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
        uploaded_file.seek(0)
        temp_file.write(uploaded_file.read())
        temp_file_path = temp_file.name
    text = extract_text(temp_file_path)
    return Job.objects.create(
        group=job_group,
        context={"source": text},
    )


def process_zip_file(uploaded_file, job_group):
    jobs = []
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(uploaded_file, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
            for root, _, files in os.walk(temp_dir):
                for file_name in files:
                    if file_name.startswith("."):
                        continue
                    file_path = os.path.join(root, file_name)
                    with open(file_path, "rb") as f:
                        django_file = File(f, name=Path(file_name).name)
                        jobs.append(process_file(django_file, job_group))
    return jobs


@permission_required("llmtools.add_jobgroup")
def tool_input_view(request, pk):
    tool = get_object_or_404(Tool, pk=pk)
    form = ToolInputForm(request.POST or None, request.FILES or None, tool=tool)

    if request.method == "POST":
        if not form.is_valid():
            return render(request, "tool_result.html", {"tool": tool, "form": form})

        job_group = JobGroup.objects.create(tool=tool, owner=request.user)
        langfuse_context.update_current_observation(session_id=str(job_group.uuid))

        uploaded_file = request.FILES.get("file", None)
        if uploaded_file:
            file_type = mime.from_buffer(uploaded_file.read(1024))
            uploaded_file.seek(0)
            if file_type == "application/zip":
                jobs = process_zip_file(uploaded_file, job_group)
            else:
                jobs = [process_file(uploaded_file, job_group)]
        else:
            cleaned_data_str = {key: str(value) for key, value in form.cleaned_data.items()}
            jobs = [Job.objects.create(group=job_group, context=cleaned_data_str, tool=tool)]

        for i in jobs:
            run_job.delay(i.id)

        return redirect(job_group.get_absolute_url())
    else:
        return render(request, "tool_form.html", {"tool": tool, "form": form})
