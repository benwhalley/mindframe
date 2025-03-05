import re
from string import Template

from django import forms
from django.shortcuts import get_object_or_404, redirect, render

from llmtools.llm_calling import chatter

from .models import Tool


class ToolInputForm(forms.Form):
    def __init__(self, *args, tool=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tool is not None:
            for field_name in tool.get_input_fields():
                self.fields[field_name] = forms.CharField(
                    label=field_name, widget=forms.Textarea(attrs={"rows": 10}), required=False
                )


def tool_input_view(request, pk):
    tool = get_object_or_404(Tool, pk=pk)

    if request.method == "POST":
        form = ToolInputForm(request.POST, tool=tool)
        if form.is_valid():
            filled_prompt = Template(tool.prompt).safe_substitute(**form.cleaned_data)
            results = chatter(filled_prompt, tool.model)
            return render(
                request, "tool_result.html", {"tool": tool, "results": results, "form": form}
            )
    else:
        form = ToolInputForm(tool=tool)

    return render(request, "tool_result.html", {"tool": tool, "form": form})
