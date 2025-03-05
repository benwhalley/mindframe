from django import template
from django.db.models import Q
from django.utils.safestring import mark_safe

from mindframe.models import Turn
from mindframe.tree import conversation_history

register = template.Library()


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
        t = list(t)[:n]
        # query again because otherwise we return a list not a queryset
        t = Turn.objects.filter(id__in=[turn.id for turn in t])

    formatted_turns = "\n\n".join(
        [
            f"{t.depth}. {t.speaker.transcript_speaker_label()} {t.text}"
            for i, t in enumerate(t.order_by("timestamp"), start=1)
        ]
    )
    return mark_safe(formatted_turns)


@register.simple_tag(takes_context=True)
def turns_with_reminder(context, reminder_text, every_n_turns, filter_type="all", total_turns=None):

    # Access `session` from the context
    turn = context.get("current_turn")

    if filter_type == "all":
        trns = conversation_history(turn).order_by("timestamp")

    elif filter_type == "step":
        raise NotImplementedError("Filtering by step is not yet implemented.")

    if total_turns:
        trns = list(trns)[:n]
        # query again because otherwise we return a list not a queryset
        trns = Turn.objects.filter(id__in=[turn.id for turn in trns])

    formatted_turns = [
        f"{t.depth}. {t.speaker.transcript_speaker_label()} {t.text}"
        for i, t in enumerate(trns, start=1)
    ]

    def insert_reminder(lst, reminder_text, every_n_turns):
        result = []
        for i, item in enumerate(lst, start=1):
            result.append(item)
            if i % every_n_turns == 0:
                result.append(reminder_text)
        return result

    return mark_safe("\n\n".join(insert_reminder(formatted_turns, reminder_text, every_n_turns)))


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
