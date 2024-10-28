# example code for loading a schema from json
# and creating a pydantic model from it

import json
from typing import Any, Type
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


# nt = '{"properties": {"text": {"title": "Text", "type": "string"}}, "required": ["text"], "title": "Note", "type": "object"}'
# NoteModel = pydantic_model_from_schema(nt)


def prompt_function_factory(return_type: Type[Any], prompt_text: str):
    @prompt(prompt_text)
    def generated_function(input_value: str) -> return_type:
        pass  # Placeholder for @prompt to fill with a response based on return type
    return generated_function



# TESTING
if False:

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



    judgement = Judgement.objects.get(id=2)
    newnote = judgement.process_inputs(session = TreatmentSession.objects.first(),
                            inputs={"input_value": anno_eg})

    newnote.data

