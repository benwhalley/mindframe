# llmtools/api.py

from typing import Dict
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from llmtools.llm_calling import chatter

from .models import Tool, ToolKey

router = Router()


class ToolKeyBody(Schema):
    """
    We receive a tool_key plus a dict of placeholders => user input.
    """

    tool_key: UUID
    fields: Dict[str, str]


class ToolResponseSchema(Schema):
    response: str


@router.post("/tool_input/{tool_pk}", response=ToolResponseSchema)
def tool_input_api(request, tool_pk: int, data: ToolKeyBody):
    # Fetch the tool by PK
    tool = get_object_or_404(Tool, pk=tool_pk)

    # Check that the provided UUID is valid for this tool
    get_object_or_404(ToolKey, tool=tool, tool_key=data.tool_key)

    # Fill placeholders in the prompt
    filled_prompt = tool.prompt.format(**data.fields)

    # Call your LLM function
    result = chatter(filled_prompt, tool.model, tool.credentials)

    return {"response": str(result.response)}


if False:

    convo = """
    therapist	00:01:20	So I get a sense it's a little anxious being here today and, uh, meeting someone like me, and, um, what we're gonna be doing today is-is inducting, but also I wanna talk about, um, yeah, the issues that-that have got you here and we need to do some sorting out around, um, yeah how serious you are to sort of sort those issues. So?
    client	00:01:38	I don't really know what issues I need to sort.
    therapist	00:01:40	Sorry?
    client	00:01:41	I don't really know what issues I need to-
    therapist	00:01:42	All right.
    client	00:01:42	-sort. It's just a bit of cash.
    therapist	00:01:44	Yeah.
    client	00:01:44	So‚Äî
    therapist	00:01:44	So first, it might be trying to sort out what are the important issues to sort out.
    client	00:01:49	Mm-hmm.
    therapist	00:01:49	Yeah, that makes sense? Yeah? So how confident are you that-that, you know, you can sort out the issues related to, um, you know, uh, taking the money from your employer? And another thing, in your precinct's report, there were some issues around gambling, and some issues around alcohol use. So those seem to be important issues that are kind of getting out. So how confident are you that you can get those sorted in the nine months we've got?
    client	00:02:17	Um, I don't think there is much to sort. I have a few drinks like everybody else my age.
    therapist	00:02:24	Yeah.
    client	00:02:26	Pokies are at the pubs for the thrills, it's no worries.
    therapist	00:02:29	Yeah, yeah.
    client	00:02:29	It's not an issue.
    therapist	00:02:30	Yeah. See one of the things I'll be really interested in-in talking with you about is, um, yeah, what's-what's the, um, what's the worst thing that has happened in terms of pokies, in terms of you know behavior around the pokies, what's the worst thing that's happened?
    client	00:02:47	Uh, I suppose when you've got no money in the pocket at the end of the night.
    therapist	00:02:50	Yeah, yeah.
    client	00:02:51	And some nights you do, so.
    therapist	00:02:53	Yeah. So how often do you end up with no money in your pocket? Can be the times when you end up with money in your pocket
    """

    import requests

    r = requests.post(
        "http://127.0.0.1:8080/api/llmtools/tool_input/1",
        json={"tool_key": "70394199-03c5-4904-9127-180b52686c72", "fields": {"source": convo}},
    ).json()
    r.content
