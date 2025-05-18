import re
import json
from string import Template
from django.core.files import File
from pathlib import Path

from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from .models import JobGroup, Job
from django.views.generic import DetailView
from .tasks import run_job_group
from .models import JobGroup
from django.core.files.uploadedfile import UploadedFile
import zipfile
import os
import tempfile
from llmtools.extract import extract_text

from llmtools.llm_calling import chatter

from .models import Tool


class ToolInputForm(forms.Form):
    def __init__(self, *args, tool=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"] = forms.FileField(label="Upload ZIP", required=False)
        if tool is not None:
            for field_name in tool.get_input_fields():
                self.fields[field_name] = forms.CharField(
                    label=field_name,
                    widget=forms.Textarea(attrs={"rows": 10}),
                    required=False,
                )


class JobGroupDetailView(DetailView):
    model = JobGroup
    template_name = "jobgroup_detail.html"
    context_object_name = "jobgroup"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["jobs"] = self.object.jobs.all()
        context["all_complete"] = not self.object.jobs.filter(completed__isnull=True).exists()
        return context


def tool_input_view(request, pk):
    tool = get_object_or_404(Tool, pk=pk)

    if request.method == "POST":
        form = ToolInputForm(request.POST, tool=tool)
        if form.is_valid():
            uploaded_file = request.FILES.get("file")
            # import pdb; pdb.set_trace()
            if uploaded_file and isinstance(uploaded_file, UploadedFile):
                job_group = JobGroup.objects.create(tool=tool)
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
                                    text = extract_text(
                                        file_path
                                    )  # ← if you want to store extracted text too
                                    Job.objects.create(
                                        group=job_group, source_file=django_file, source=text
                                    )
                run_job_group.delay(job_group.id)
                return redirect(job_group.get_absolute_url())
            cleaned_data_str = {key: str(value) for key, value in form.cleaned_data.items()}
            filled_prompt = Template(tool.prompt).safe_substitute(**cleaned_data_str)
            results = chatter(filled_prompt, tool.model)

            return render(
                request,
                "tool_result.html",
                {"tool": tool, "results": json.dumps(results, indent=2), "form": form},
            )
    else:
        form = ToolInputForm(tool=tool)

    return render(request, "tool_result.html", {"tool": tool, "form": form})
