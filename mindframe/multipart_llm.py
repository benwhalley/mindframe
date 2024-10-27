import re
from magentic import prompt
from magentic import OpenaiChatModel
from magentic.chat_model.litellm_chat_model import LitellmChatModel

from pydantic import BaseModel
from typing import List, Optional
from collections import OrderedDict, namedtuple

ChatResult = namedtuple('ChatResult', ['value', 'prompt'])

free = LitellmChatModel("ollama_chat/llama3.2", api_base="http://localhost:11434")
expensive=OpenaiChatModel("gpt-4o")
cheap=OpenaiChatModel("gpt-4o-mini")

@prompt("""{prompt}""")
def chat(prompt: str) -> str: ...

# chat("say hello")

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


def chatter(multipart_prompt, model=cheap):    
    prompts_dict = split_multipart_prompt(multipart_prompt)
    results_dict = OrderedDict()  # Dictionary to hold accumulated results
    
    prompt_parts = []
    for key, value in prompts_dict.items():
        prompt_parts.append(value)
        prompt  = "\n".join(prompt_parts)
        with model:
            res = chat(prompt)
        results_dict[key] = ChatResult(value= res, prompt= prompt )
        prompt_parts.append(res)

    return results_dict

# results_dict = chatter("""Think about mammals[THOUGHTS] Now tell me a joke[JOKE]""")
# results_dict.keys()
# results_dict['THOUGHTS'].value
# results_dict['JOKE'].value