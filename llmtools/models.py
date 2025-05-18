import json
import re
import uuid
from django.utils import timezone
from django.db import models
from django.urls import reverse
from .llm_calling import chatter
from .extract import extract_text
from string import Template


class Tool(models.Model):
    name = models.CharField(max_length=100)
    prompt = models.TextField(
        help_text="Use curly braces for placeholders, e.g.: 'Hello {user_name}, how are you?'"
    )
    model = models.ForeignKey("mindframe.LLM", on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    def get_input_fields(self):
        # finds all {placeholder_name} in prompt
        return re.findall(r"\{([^}]+)\}", self.prompt)

    def get_absolute_url(self):
        return reverse("tool-input", kwargs={"pk": self.pk})


class ToolKey(models.Model):
    """
    This model links a Tool with a secure UUID key
    so that clients can post data to the Ninja API with that key.
    """

    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name="tool_keys")
    tool_key = models.UUIDField(default=uuid.uuid4, unique=True)

    def __str__(self):
        return f"{self.tool.name} - {self.tool_key}"


class JobGroup(models.Model):
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    complete = models.BooleanField(default=False)

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


class Job(models.Model):
    group = models.ForeignKey(JobGroup, on_delete=models.CASCADE, related_name="jobs")
    source = models.TextField()
    source_file = models.FileField(upload_to="source_files", max_length=1024 * 4)
    result = models.JSONField(null=True)
    completed = models.DateTimeField(null=True)

    def text(self):
        return self.source_file and extract_text(self.source_file.path) or self.source or ""

    def filename(self):
        return self.source_file and self.source_file.path or ""

    def process(self):
        try:
            tool = self.group.tool
            filled_prompt = Template(tool.prompt).safe_substitute(
                **{"source": self.text(), "file_path": self.filename()}
            )

            result = dict(chatter(filled_prompt, tool.model))
            if len(result.keys()) > 1:
                del result["RESPONSE_"]
            result["source"] = self.text()
            result["file_path"] = self.filename()

            self.result = result
            self.completed = timezone.now()
            self.save()
            print(self.result)

        except Exception as e:
            print(str(e))
            raise e
            result = {}

        return result
