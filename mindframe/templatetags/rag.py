import logging

from django import template
from django.db.models import Q
from django.utils.safestring import mark_safe

from mindframe.models import LLM, Memory, MemoryChunk

logger = logging.getLogger(__name__)
register = template.Library()


@register.simple_tag(takes_context=True)
def memory(context, query=None, search_type="hyde", n=3):
    """
    Custom template tag to retrieve relevant MemoryChunk objects using semantic search or HyDE search.

    :param context: The template context containing session information.
    :param query: The search query string.
    :param search_type: Type of search ("semantic" or "hyde").
    :param n: Number of results to return.
    :return: Filtered queryset of MemoryChunk objects.
    """

    session = context.get("session", False)
    if not session:
        logger.error("Session not found in context.")
        return ""

    intervention = session.cycle.intervention
    memories = Memory.objects.filter(intervention=intervention)

    results, _, _ = memories.search(
        query, top_k=n, method=search_type, llm=LLM.objects.get(model_name="gpt-4o")
    )

    return results
