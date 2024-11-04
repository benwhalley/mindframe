import re

import dotenv
dotenv.load_dotenv('.env')

from magentic import prompt

from pydantic import BaseModel
from typing import List, Optional
from collections import OrderedDict, namedtuple
from django.conf import settings
import tiktoken

encoding = tiktoken.encoding_for_model('gpt-4o-mini')

class ChatResult(BaseModel):
    value: str
    prompt: str
    input_tokens: int
    output_tokens: int


@prompt("""{prompt}""")
def chat(prompt: str) -> str: ...

# with settings.MINDFRAME_AI_MODELS.cheap:
#     chat("say hello")

# Function to split the document into an ordered dictionary by `[VARNAME]` blocks
def split_multipart_prompt(text):
    
    # this is gross to use regex
    # we should use pandoc instead and traverse a tree nicely
    # import pandoc
    # from pandoc.types import *

    varname_pattern = r'\[\s*(\w+)\s*\]'
    parts = re.split(varname_pattern, text)
    # if we didn't explicitly include enough response variables, add one
    if len(parts) % 2 == 0:
        parts.append("__RESPONSE__")

    # iterate over tuples and return an ordered dictionary
    result = OrderedDict(zip(parts[1::2], parts[::2]))
    for text_segment, varname in zip(parts[::2], parts[1::2]):
        result[varname.strip()] = text_segment.strip()

    return result


def chatter(multipart_prompt, model=settings.MINDFRAME_AI_MODELS.cheap):    
    prompts_dict = split_multipart_prompt(multipart_prompt)
    results_dict = OrderedDict()  # Dictionary to hold accumulated results
    
    prompt_parts = []

    for key, value in prompts_dict.items():
        prompt_parts.append(value)
        prompt  = "\n".join(prompt_parts)
        with model:
            res = chat(prompt)
        results_dict[key] = ChatResult(value= res, 
                                       prompt= prompt, 
                                       input_tokens=len(encoding.encode(prompt)), output_tokens=len(encoding.encode(res)) 
                                       )
        prompt_parts.append(res)

    return results_dict

# results_dict = chatter("""Think about mammals[THOUGHTS] Now tell me a joke[JOKE]""")
# results_dict.keys()
# results_dict['THOUGHTS'].value
# results_dict['JOKE'].value