import json
import re
import uuid
from string import Template

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django_extensions.db.models import TimeStampedModel


from .extract import extract_text
from .llm_calling import chatter


class Tool(models.Model):
    name = models.CharField(max_length=100)
    prompt = models.TextField(
        help_text="Use ${curly} braces for source placeholder, e.g.: 'User input document text: ${user_name}. Extract the title: [[extract:title]]'"
    )
    model = models.ForeignKey("mindframe.LLM", on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    def get_input_fields(self):
        # finds all {placeholder_name} in prompt
        return re.findall(r"\{\{([^}]+)\}\}", self.prompt)

    def get_absolute_url(self):
        return reverse("tool_input", kwargs={"pk": self.pk})


class ToolKey(models.Model):
    """
    This model links a Tool with a secure UUID key
    so that clients can post data to the Ninja API with that key.
    """

    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name="tool_keys")
    tool_key = models.UUIDField(default=uuid.uuid4, unique=True)

    def __str__(self):
        return f"{self.tool.name} - {self.tool_key}"


class JobGroup(TimeStampedModel):
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    complete = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_groups"
    )

    def get_absolute_url(self):
        return reverse("jobgroup-detail", kwargs={"pk": self.pk})

    def json(self):
        return json.dumps(list(self.jobs.all().values_list("result", flat=True)), indent=2)

    def run(self):
        for job in self.jobs.all():
            job.process()

        if self.jobs.filter(completed__isnull=True).count() == 0:
            self.complete = True
            self.save()
            for i in self.jobs.all():
                i.source_file.delete()


class Job(TimeStampedModel):
    group = models.ForeignKey(JobGroup, on_delete=models.CASCADE, related_name="jobs")
    source = models.TextField()
    source_file = models.FileField(upload_to="source_files", max_length=1024 * 4)
    result = models.JSONField(null=True)
    completed = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.source_file or self.source[:50]}..."

    def text(self):
        return self.source_file and extract_text(self.source_file.path) or self.source or ""

    def filename(self):
        return self.source_file and self.source_file.name or ""

    def filepath(self):
        return self.source_file and self.source_file.path or None

    def process(self):
        try:
            tool = self.group.tool
            filled_prompt = Template(tool.prompt).safe_substitute(
                **{"source": self.text(), "file_path": self.filepath()}
            )

            result = dict(chatter(filled_prompt, tool.model))
            if len(result.keys()) > 1:
                del result["RESPONSE_"]
            result["source"] = self.text()
            result["file_name"] = self.filename()

            self.result = result
            self.completed = timezone.now()
            self.save()
            print(self.result)

        except Exception as e:
            print(str(e))
            raise e
            result = {}

        return result
