# example code for loading a schema from json
# and creating a pydantic model from it

import json
from typing import Any, Optional, Type, List

from magentic import prompt
from pydantic import BaseModel, create_model, Field


def pydantic_model_from_schema(schema):
    type_mapping = {
        "string": (str, None),
        "integer": (
            int,
            Field(..., ge=0),
        ),  # Example for integer fields with a minimum constraint
        # Add more types as needed
    }
    fields = {}
    for prop, config in schema["properties"].items():
        field_type, field_info = type_mapping.get(
            config["type"], (str, None)
        )  # Default to str if type unknown
        if prop in schema.get("required", []):
            fields[prop] = (field_type, ...)
        else:
            fields[prop] = (field_type, field_info)
    # Create the Pydantic model, specifying __module__ explicitly
    DynamicModel = create_model(schema["title"], **fields, __module__=__name__)
    return DynamicModel


def data_extraction_function_factory(
    return_type: Type[Any], prompt_template: str = "{input}\nRespond in JSON"
):
    """Make functions which extract data in specific format

    Return a function which accepts a prompt string and calls an LLM, returning a Pydantic model instance of return_type
    """
    @prompt(prompt_template)
    def generated_function(input: str) -> return_type:
        pass  # Placeholder for @prompt to fill with a response based on return type
    return generated_function


if False:  # TESTS TODO CONVERT TO PROPER TESTS
    # some example data
    anno_eg = """therapist	00:00:02	You did your values clarification handout, and that was part of what I wanted to go over with you today. I wanted to hear about your values and just talk to you a little bit more about that. Do-do you wanna tell me what some of your top five values are?
    client	00:00:17	Yes, um, my top value is family happiness, um, that's-
    therapist	00:00:23	That's number one?
    client	00:00:24	-that's number one to me, especially now. I usually do this values clarification sheet, like, every two to three months-
    therapist	00:00:33	Mm-hmm.
    client	00:00:34	#NAME?
    therapist	00:00:39	Oh. So, right now family value is the most important thing to you?
    client	00:00:43	Yes.
    therapist	00:00:43	Family happiness?
    client	00:00:45	Yes, it's the most important because it's a little lacking, so I know that that's something that is very important to me.
    therapist	00:00:55	Okay. Would you like to talk more about that?"""

    # we would define a return type in pydantic for the judgement
    class BriefNote(BaseModel):
        text: str

    # can serialise like this and save in the DB as a return type for a judgement
    schema_string = BriefNote.schema_json()

    # then we can reconstruct the pydantic model from the schema string
    BriefNoteReconstructed = pydantic_model_from_schema(json.loads(schema_string))
    schema_string == BriefNoteReconstructed.schema_json()  # True

    # worked example
    jjrt = JudgementReturnType.objects.create(schema = json.loads(schema_string), title="BriefNote")
    jj = Judgement.objects.create(
        intervention=Intervention.objects.first(),
        title="Brief note",
        prompt_template="Write a brief clinical note from these data: {input}",
        return_type=jjrt,
    )
    newnote = jj.process_inputs(
        session=TreatmentSession.objects.first(), inputs={"input": anno_eg}
    )
    newnote.data

    # this is a more complex Note made from a judgement which specifies multiple return fields
    class ComplexNote(BaseModel):
        text: str
        number_open_questions: int
        open_question_texts: List[str]
        patient_name_if_included: str = ''
    cjjrt = JudgementReturnType.objects.create(schema = ComplexNote.schema(), title="ComplexNote")
    jj = Judgement.objects.create(
        intervention=Intervention.objects.first(),
        title="Complex note with patient ID and open question count",
        prompt_template="Write a brief clinical note from these data. Find the patient name if present. Also Count the number of open questions used by the therapist, and include the text of each open question.\n\n {input}",
        return_type=cjjrt
    )
    newnote = jj.process_inputs(
        session=TreatmentSession.objects.first(), inputs={"input": anno_eg}
    )
    newnote.data.keys()
    newnote
