from django import template
from django.db.models import Subquery, OuterRef
from mindframe.models import Note

register = template.Library()


def format_guidance(guidance):
    return "\n\n".join([f"{n.val()}" for n in guidance])


@register.filter
def guidance(session, filter_type=None):

    all_notes = Note.objects.filter(turn__session_state__session__cycle=session.cycle)
    latest_notes = all_notes.filter(
        # uncomment to restrict to judgements made in the step
        # judgement__stepjudgements__step=self,
        judgement__stepjudgements__use_as_guidance=True,
        judgement__variable_name=OuterRef("judgement__variable_name"),
    ).order_by("-timestamp")

    guidance = all_notes.filter(pk__in=Subquery(latest_notes.values("pk")[:1]))
    return format_guidance(guidance)
