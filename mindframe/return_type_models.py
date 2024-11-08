import json
from pydantic import BaseModel, create_model, Field
from typing import List, Literal, Optional
from magentic import prompt


"""
Important note

`value` is a semi-magic field name for these models. It is currently used in 
Session.get_judgements() to decide which judgements have already been completed
successfully, and excluded if they only needed to be run once.

"""


class CommentedBooleanResponse(BaseModel):
    commentary: str = Field(
        ...,
        description="Think carefully about your classification and give a 1 or 2 sentence explanation of your rationale here.",
    )
    value: bool = Field(
        ..., description="Only return true if you are confident in your classification."
    )


class ComplexNote(BaseModel):
    value: str
    number_open_questions: int
    open_question_texts: List[str]
    patient_name_if_included: str = ""


class BriefNote(BaseModel):
    value: str


class OptionalText(BaseModel):
    value: Optional[str]


def forced_choice_model(valid_options):
    literals = Literal[tuple(valid_options)]

    # Create a dynamic model with the constrained field `value`, setting `__module__` explicitly
    return create_model("ForcedChoice", value=(literals, ...), __module__=__name__)


# # Example usage
# ForcedChoice = forced_choice_model(["Yes", "No"])
# x_ = ForcedChoice(value="Yes")  # Passes
# x_ = ForcedChoice(value="XXX")  # Fails


JUDGEMENT_RETURN_TYPES = {
    "CommentedBooleanResponse": CommentedBooleanResponse,
    "ComplexNote": ComplexNote,
    "BriefNote": BriefNote,
    "OptionalText": OptionalText,
    "ForcedChoice": forced_choice_model,
}


# CommentedBooleanResponse(commentary="", response=True)
# CommentedBooleanResponse.schema_json()


if False:

    @prompt("""{s}""")
    def judge(s) -> CommentedBooleanResponse: ...

    judge(
        """
    CLIENT: hi
    BOT: Hi Ben, it&#x27;s nice to meet you! How do you prefer to be addressed?
    CLIENT: I like being called Ben
    BOT: It&#x27;s great to meet you, Ben; I&#x27;m here to help you feel comfortable, so I&#x27;m curious, what do you enjoy doing in your spare time?
    CLIENT: paragliding
    CLIENT: yes?
    CLIENT: ss
    CLIENT: s
    CLIENT: sa
    CLIENT: I&#x27;m ready to start now 

    Is the client ready to start now?
    Respond in JSON
    """
    )
