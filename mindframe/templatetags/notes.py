from django import template
from django.db.models import Max, OuterRef, Q, Subquery

from mindframe.models import Note

register = template.Library()


@register.simple_tag(takes_context=True)
def notes(context, variable_name=None, only_most_recent=True, string=True):

    session = context.get("session")
    if not session:
        raise ValueError("Session is not available in the context.")

    notes = Note.objects.filter(turn__session_state__session=session)

    if variable_name:
        notes = notes.filter(judgement__variable_name=variable_name)

    if only_most_recent:
        # Subquery to get the latest timestamp for each variable_name
        latest_note = (
            Note.objects.filter(
                judgement__variable_name=OuterRef("judgement__variable_name"),
                turn__session_state__session=session,
            )
            .order_by("-timestamp")
            .values("id")[:1]
        )

        notes = notes.filter(id__in=Subquery(latest_note))

    if string:
        return "--------------\n\n".join(map(str, notes.values("judgement__variable_name", "data")))
    return notes
