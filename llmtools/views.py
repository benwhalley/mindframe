import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from string import Template

import pandas as pd
from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.files import File
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView
from langfuse.decorators import langfuse_context, observe

langfuse_context.configure(debug=False)

from django import forms
from django.core.exceptions import ValidationError

from llmtools.extract import extract_text

from .models import Job, JobGroup, Tool
from .tasks import run_job


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
                    widget=forms.Textarea(attrs={"rows": 5}),
                    required=False,
                )
                self.dynamic_fields.append(field_name)

    def clean(self):
        cleaned_data = super().clean()
        file_ = cleaned_data.get("file")
        dynamic_filled = [cleaned_data.get(f) for f in self.dynamic_fields if cleaned_data.get(f)]
        if not file_ and len(dynamic_filled) < len(self.dynamic_fields):
            raise ValidationError(
                "You must either upload a file, or fill in all manual input fields."
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


@observe(capture_input=False, capture_output=False)
@permission_required("llmtools.add_jobgroup")
def tool_input_view(request, pk):
    tool = get_object_or_404(Tool, pk=pk)

    if request.method == "POST":
        form = ToolInputForm(request.POST or None, request.FILES or None, tool=tool)
        if form.is_valid():
            uploaded_file = request.FILES.get("file")

            if uploaded_file and isinstance(uploaded_file, UploadedFile):
                job_group = JobGroup.objects.create(tool=tool, owner=request.user)
                langfuse_context.update_current_observation(session_id=str(job_group.uuid))

                try:
                    with zipfile.ZipFile(uploaded_file, "r") as zip_ref:
                        pass  # process zip below

                except zipfile.BadZipFile:
                    # Create a job group for a single file upload
                    ext = os.path.splitext(uploaded_file.name)[1] or ".bin"
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                        uploaded_file.seek(0)
                        temp_file.write(uploaded_file.read())
                        temp_file_path = temp_file.name
                    text = extract_text(temp_file_path)
                    # os.remove(temp_file_path)
                    Job.objects.create(
                        group=job_group,
                        # source_file=django_file,
                        context={"source": text},
                    )

                    # schedule jobs to run
                    run_job.delay(job_group.jobs.first().id)
                    return redirect(job_group.get_absolute_url())

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
                                    text = extract_text(file_path)
                                    Job.objects.create(
                                        group=job_group,
                                        source_file=django_file,
                                        context={"source": text},
                                    )
                # schedule jobs to run
                [run_job.delay(i.id) for i in job_group.jobs.all()]
                return redirect(job_group.get_absolute_url())
            else:
                cleaned_data_str = {key: str(value) for key, value in form.cleaned_data.items()}

                newjob = Job.objects.create(group=None, context=cleaned_data_str, tool=tool)

                # do this synchronously and wait now
                newjob.save()
                result = newjob.run()
                jsonres = json.dumps([result], indent=2)
                csvres = pd.DataFrame([result]).to_csv()
                return render(
                    request,
                    "tool_result.html",
                    {"tool": tool, "results": jsonres, "form": form, "csv": csvres},
                )
    else:
        form = ToolInputForm(tool=tool)

    return render(request, "tool_result.html", {"tool": tool, "form": form})
