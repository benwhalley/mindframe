# models.py
import re
from django.db import models
from django.urls import reverse
from mindframe.models import LLM
import uuid


class Tool(models.Model):
    name = models.CharField(max_length=100)
    prompt = models.TextField(
        help_text="Use curly braces for placeholders, e.g.: 'Hello {user_name}, how are you?'"
    )
    model = models.ForeignKey(LLM, on_delete=models.CASCADE)

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
