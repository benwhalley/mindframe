from django import template
from django.db.models import Q

register = template.Library()

from mindframe.rag import rag_examples


@register.simple_tag(takes_context=True)
def examples(context, query, n=2, window=1):

    session = context.get("session")
    if not session:
        raise ValueError("Session is not available in the context.")

    intervention = session.cycle.intervention
    if not query.strip():
        return "No query provided, no examples found."

    examples = rag_examples(query, top_k=n, window_size=window, interventions=[intervention])

    return "\n\n-----------\n\n".join(examples)
