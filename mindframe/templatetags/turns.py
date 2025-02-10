from django import template
from django.db.models import Q
from mindframe.models import Turn
from django.utils.safestring import mark_safe

from mindframe.tree import conversation_history

register = template.Library()


def format_turns(turns):
    if not turns.count():
        return "No conversation history yet."

    formatted_turns = "\n\n".join(
        [f"{t.speaker.role.upper()}: {t.text}" for t in turns.order_by("timestamp")]
    )
    return mark_safe(formatted_turns)


@register.simple_tag(takes_context=True)
def turns(context, filter_type="all", n=None):

    # Access `session` from the context
    turn = context.get("current_turn")

    if filter_type == "all":
        t = conversation_history(turn)

    elif filter_type == "step":
        raise NotImplementedError("Filtering by step is not yet implemented.")
        t = turns.filter(session_state__step=session.current_step())

    if n:
        t = turns[: n - 1]
        # query again because otherwise we return a list not a queryset
        t = Turn.objects.filter(id__in=[turn.id for turn in t])

    return format_turns(t)


# @register.filter
# def turns(session, filter_type):
#     turns = Turn.objects.filter(session_state__session__id=session.id).order_by("timestamp")

#     if filter_type == "all":
#         t = turns

#     if filter_type == "step":
#         t = turns.filter(session_state__step=session.current_step())

#     # handle 'recent:10' syntax
#     if filter_type.startswith("recent:"):
#         try:
#             limit = int(filter_type.split(":")[1])
#             t = turns[:limit]
#         except (IndexError, ValueError):
#             t = turns

#     return format_turns(t)


# @register.filter
# def format_turns(turns):
#     return format_turns(turns)


@register.simple_tag
def find_turns(session, query=None, window=0):
    """
    Custom template tag to retrieve filtered Turn objects.
    :param session: The TreatmentSession instance.
    :param query: Text query to filter turns by.
    :param window: Number of turns to include before/after matches.
    :return: Filtered queryset of Turn objects.
    """
    turns = session.turns.order_by("timestamp")

    # If no filters are specified, return all turns
    if not query:
        return turns

    # Filter turns matching the query
    matches = turns.filter(Q(text__icontains=query))

    if not matches.exists() or window == 0:
        return matches

    # Collect IDs within the window for each match
    all_ids = set()
    turn_ids = list(turns.values_list("id", flat=True))
    for match in matches:
        match_index = turn_ids.index(match.id)
        start = max(0, match_index - window)
        end = match_index + window + 1
        all_ids.update(turn_ids[start:end])

    # Return filtered queryset with IDs in the collected range
    return turns.filter(id__in=all_ids)
