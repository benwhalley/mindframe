from mindframe.models import Turn, Conversation
from langfuse import Langfuse

langfuse = Langfuse()


def get_langfuse_trace(turn: Turn):
    """
    Get the Langfuse trace for a Turn
    """

    return langfuse.fetch_trace(session_id=turn.uuid)


# xx = [get_langfuse_trace(i) for i in Turn.objects.filter(step__isnull=False).order_by('-timestamp')[:10]]

# turn = Turn.objects.all().last()
# trace = langfuse.fetch_traces(session_id=turn.uuid).data[0]
# obs = langfuse.fetch_observations(trace_id=trace.id)

# [i for i in obs.data if i.type=="GENERATION"][0]
