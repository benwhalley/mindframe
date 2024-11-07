import json
from pydantic import BaseModel
from pydantic import BaseModel, create_model, Field
from typing import List, Literal
from magentic import prompt


class CommentedBooleanResponse(BaseModel):
    commentary: str = Field(
        ...,
        description="Think carefully about your classification and give a 1 or 2 sentence explanation of your rationale here."
    )
    response: bool = Field(
        ..., description="Only return true if you are confident in your classification.")


class ComplexNote(BaseModel):
    text: str
    number_open_questions: int
    open_question_texts: List[str]
    patient_name_if_included: str = ''


class BriefNote(BaseModel):
    text: str


JUDGEMENT_RETURN_TYPES = {
    "CommentedBooleanResponse": CommentedBooleanResponse,
    "ComplexNote": ComplexNote,
    "BriefNote": BriefNote,
}


# CommentedBooleanResponse(commentary="", response=True)
# CommentedBooleanResponse.schema_json()





if False:
        
    @prompt("""{s}""")
    def judge(s) -> CommentedBooleanResponse: ...



    judge("""
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
    """)