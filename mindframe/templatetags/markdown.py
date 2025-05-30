import logging

import nh3
from django import template
from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt

register = template.Library()

logger = logging.getLogger(__name__)


@register.filter
def markdown(text: str):
    try:
        md = MarkdownIt()
        html = md.render(str(text))
        html = nh3.clean(html)  # Sanitize HTML
        return mark_safe(html)
    except Exception as e:
        logger.warning(f"Error rendering markdown: {e}")
        return "!!" + str(text)
