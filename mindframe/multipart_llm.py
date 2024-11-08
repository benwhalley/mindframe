import re

import dotenv

dotenv.load_dotenv(".env")

from magentic import prompt

from pydantic import BaseModel
from typing import List, Optional
from collections import OrderedDict, namedtuple
from django.conf import settings
import tiktoken

import logging

logger = logging.getLogger(__name__)

encoding = tiktoken.encoding_for_model("gpt-4o-mini")


class ChatResult(BaseModel):
    value: str
    prompt: str
    input_tokens: int
    output_tokens: int


# aa=ChatResult(value="s", prompt="sas", output_tokens=1, input_tokens=1)
# import json
# json.dumps(aa.json())


@prompt("""{prompt}""")
def chat(prompt: str) -> str: ...


# with settings.MINDFRAME_AI_MODELS.cheap:
#     chat("say hello")


# Function to split the document into an ordered dictionary by `[VARNAME]` blocks
def split_multipart_prompt(text) -> OrderedDict:

    # this is a bit gross to use regex
    # we should maybe use pandoc instead and traverse a tree nicely, see
    # import pandoc
    # from pandoc.types import *
    # it works fine for now though

    varname_pattern = r"\[\[\s*(\w+)\s*\]\]"
    parts = re.split(varname_pattern, text)
    # if we didn't explicitly include a final response variable, add one here
    if len(parts) % 2 == 1:
        parts.append("__RESPONSE__")

    # iterate over tuples and return an ordered dictionary
    result = OrderedDict(zip(parts[1::2], parts[::2]))
    for text_segment, varname in zip(parts[::2], parts[1::2]):
        result[varname.strip()] = text_segment.strip()

    return result


def chatter(multipart_prompt, model=settings.MINDFRAME_AI_MODELS.cheap):
    """Split a prompt template into parts and iteratively complete each part, using previous prompts and completions as context for the next."""

    prompts_dict = split_multipart_prompt(multipart_prompt)
    results_dict = OrderedDict()

    prompt_parts = []

    for key, value in prompts_dict.items():
        prompt_parts.append(value)
        prompt = "\n".join(prompt_parts)
        with model:
            logger.debug(f"Calling LLM ({model}): {prompt[:30]}")
            try:
                res = chat(prompt)
            except Exception as e:
                logger.error(f"Error calling LLM: {e}")
                logger.error(f"Prompt: {prompt}")
        results_dict[key] = ChatResult(
            value=res,
            prompt=prompt,
            input_tokens=len(encoding.encode(prompt)),
            output_tokens=len(encoding.encode(res)),
        )
        prompt_parts.append(res)

    return results_dict


# results_dict = chatter("""Think about mammals[THOUGHTS] Now tell me a joke[JOKE]""")
# results_dict.keys()
# results_dict['THOUGHTS'].value
# results_dict['JOKE'].value
