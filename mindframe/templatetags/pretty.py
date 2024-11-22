import json
from django import template
import pandoc
from django.utils.safestring import mark_safe


register = template.Library()


@register.filter
def md(value):
    """
    A template filter to convert Markdown to HTML.
    """
    return mark_safe(pandoc.write(pandoc.read(value), format="html"))


@register.filter
def pretty_json(value):
    """
    A template filter to pretty-print JSON.
    """
    try:
        return json.dumps(value, indent=2)
    except (ValueError, TypeError):
        return value
