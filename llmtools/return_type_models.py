import json
from pydantic import BaseModel, create_model, Field
from typing import List, Literal, Optional


# Standard RTs for template syntax


class DefaultResponse(BaseModel):
    """Respond to the context intelligently and concisely."""

    response: str = Field(
        ...,
        description="An intelligent completion that responds to the context in a concise manner.",
    )


class ExtractedResponse(BaseModel):
    """Extract information from the context verbatim."""

    response: str = Field(
        ...,
        description="Text extracted from the context verbatim. Copy text exactly as it appears in the context. Never paraphrase or summarize. Never include any additional information.",
    )


class SpokenResponse(BaseModel):
    """A spoken response, continuing the previous conversation naturally and fluently."""

    response: str = Field(
        ...,
        description="A spoken response, continuing the previous conversation. Don't label the speaker or use quotes, just produce the words spoken.",
    )


class InternalThoughtsResponse(BaseModel):
    """A response containing plans, thoughts and step-by-step reasoning to solve a task."""

    response: str = Field(
        ...,
        description="Your thoughts. Never a spoken response, yet -- just careful step by step thinking, planning and reasoning, written in super-concise note form. Always on topic and relevant to the task at hand.",
    )


class PoeticalResponse(BaseModel):
    """A spoken response, continuing the previous conversation, in 16th C style."""

    response: str = Field(
        ...,
        description="A response, continuing the previous conversation but always in POETRICAL form - often a haiku.",
    )


class ConversationSegment(BaseModel):
    description: str = Field(description="A short description of the segment.")
    start: int
    end: int


class ChunkedConversationResponse(BaseModel):
    """A spoken response, continuing the previous conversation, in 16th C style."""

    response: List[ConversationSegment] = Field(
        ...,
        description="Returns a list of ConversationSegments, each with a description",
    )


def selection_response_model(valid_options):
    """Factor to produce a pydantic model with specific options required."""

    if not valid_options:
        raise ValueError("valid_options must be a non-empty list of strings")

    literals = Literal[tuple(valid_options)]

    # Create a dynamic model with the constrained field `value`, setting `__module__` explicitly
    return create_model(
        "SelectionResponse",
        response=(
            literals,
            Field(
                ...,
                description="A selection from one of the options. No discussion or explanation, just the text of the choice, exactly matching one of the options provided.",
            ),
        ),
        __module__=__name__,
    )


class BooleanResponse(BaseModel):
    """A boolean response, making a True/False decision based on the question based."""

    response: bool = Field(
        ...,
        description="Returns true or false only, based on the question/statement posed.",
    )
