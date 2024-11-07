# example code for loading a schema from json
# and creating a pydantic model from it

import json
from typing import Any, Optional, Type, List

from magentic import prompt
from pydantic import BaseModel, create_model, Field


# TODO - THIS DOESN"T WORK YET BECAUSE OF PROBLEMS SERIALISING AND DESERIALISING THE SCHEMA
# AT PRESENT WE USE A CHOICEFIELD FOR THE JUDGEMENT RETURN TYPE

# def pydantic_model_from_schema(schema):
#     type_mapping = {
#         "string": (str, None),
#         "integer": (
#             int,
#             Field(..., ge=0),
#         ),  # Example for integer fields with a minimum constraint
#         # Add more types as needed
#     }
#     fields = {}
#     for prop, config in schema["properties"].items():
#         field_type, field_info = type_mapping.get(
#             config["type"], (str, None)
#         )  # Default to str if type unknown
#         if prop in schema.get("required", []):
#             fields[prop] = (field_type, ...)
#         else:
#             fields[prop] = (field_type, field_info)
#     # Create the Pydantic model, specifying __module__ explicitly
#     DynamicModel = create_model(schema["title"], **fields, __module__=__name__)
#     print("Created Pydantic model: ", DynamicModel, DynamicModel.schema())
#     return DynamicModel


def data_extraction_function_factory(
    return_type: Type[Any], prompt_template: str = "{input}\nRespond in JSON"
):
    """Make functions which extract data in specific format

    Return a function which accepts a prompt string and calls an LLM, returning a Pydantic model instance of return_type
    """
    @prompt(prompt_template,  max_retries=5)
    def generated_function(input: str) -> return_type:
        pass  # Placeholder for @prompt to fill with a response based on return type
    return generated_function


