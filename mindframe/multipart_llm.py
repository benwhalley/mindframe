"""
# Define your desired output structure

from pydantic import BaseModel, Field
from mindframe.multipart_llm import structured_chat
from typing import Optional, List

from mindframe.multipart_llm import *


mini, _ = LLM.objects.get_or_create(provider_name="AZURE", model_name="gpt-4o-mini", nickname=",mini")

local, _ = LLM.objects.get_or_create(provider_name="OLLAMA", model_name="llama3.2", nickname=",local")



# this raises an exception
split_multipart_prompt("one[[]]two[[RESP]]dddd")

# tests
len(split_multipart_prompt("one[[x]]two[[RESP]]dddd").items())==3
split_multipart_prompt("one[[talk:y]]two[[RESP]]dddd")['talk:y'] == 'one'


rr = chatter("Pick an ancient civilisation: [[thoughts]] Now pick one of art, science or magic. Just one of those three words [[pick:topic]] Now tell me a SINGLE interesting fact[[speak:]]", mini)
rr[0]['__RESPONSE__']
rr[1]

chatter("Think about mammals very briefly, in one or 2 lines: [[THOUGHTS]] Now tell me a joke. [[speak:JOKE]]", mini)[0]['JOKE']


chatter("Think about mammals very briefly, in one or 2 lines: [[THOUGHTS]] Now tell me a joke. [[poem:JOKE]]", mini)[0]['JOKE']



simple_chat("tell a joke", mini)[0]
simple_chat("tell a joke", local)[0]


chatter("Think about mammals very briefly, in one or 2 lines: [[THOUGHTS]] Now tell me a joke[[JOKE]]", mini)[0]

chatter("Think about mammals very briefly, in one or 2 lines: [[THOUGHTS]] Now tell me a joke[[JOKE]]", local)[0]



class UserInfo(BaseModel):
    name: str
    age: Optional[int] = Field(description="The age in years of the user.", default=None)

class UserList(BaseModel):
    peeps: List[UserInfo]


structured_chat("Create a list of 3 fake users. Use consistent field names for each item. Use the tools",
                llm=mini,
                return_type=UserList)

structured_chat("Create a fake user, Use the tools",
                llm=local,
                return_type=UserInfo)



# note - not as reliable but still works OK
structured_chat("Create a list of 3 fake users. Use consistent field names for each item. Use the tools",
                llm=local,
                return_type=UserList)




# do some accounting on tokens on one chatter call from above
import pandas as pd
df = pd.DataFrame(
list(rr[1].values('metadata__usage__total_tokens', 'metadata__usage__prompt_tokens'))
)
df['out'] = df['metadata__usage__total_tokens'] - df['metadata__usage__prompt_tokens']
df[['out', 'metadata__usage__prompt_tokens']].sum()


"""

import logging
import re
from collections import namedtuple, OrderedDict
from hashlib import sha256
from typing import List

import dotenv
import tiktoken
from django.conf import settings
from pydantic import BaseModel, Field


dotenv.load_dotenv(".env")
logger = logging.getLogger(__name__)
encoding = tiktoken.encoding_for_model("gpt-4o-mini")


# Function to split the document into an ordered dictionary by `[VARNAME]` blocks
def split_multipart_prompt(text) -> OrderedDict:
    # this is a bit gross to use regex
    # we should maybe use pandoc instead and traverse a tree nicely, see
    # import pandoc
    # from pandoc.types import *
    # it works fine for now though

    if bool(re.search(r"\[\[\s?\]\]", text)):
        raise Exception("Empty response key in prompt, e.g. [[]], is not allowed. Use [[var]].")

    varname_pattern = r"\[\[\s*([\w+\:\s+]+)\s*\]\]"
    parts = list(filter(bool, map(str.strip, re.split(varname_pattern, text))))
    # if we didn't explicitly include a final response variable, add one here
    if len(parts) % 2 == 1:
        parts.append("__RESPONSE__")
    # iterate over tuples and return an ordered dictionary
    result = OrderedDict(zip(parts[1::2], parts[::2]))
    for text_segment, varname in zip(parts[::2], parts[1::2]):
        result[varname.strip()] = text_segment.strip()
    return result


# print(split_multipart_prompt("First part as aspeech[[speech:XXX]]second part as text[[yyy]]"))
# print(split_multipart_prompt("First part as aspeech[[speech: XXX]]second part as text[[yyy]]"))


def structured_chat(
    prompt,
    llm,
    return_type,
    max_retries=3,
    log_context={},
):
    from mindframe.models import LLMLog, LLMLogTypes

    logger.debug(prompt)
    try:
        res, com = llm.provider.chat.completions.create_with_completion(
            model=llm.model_name,
            response_model=return_type,
            messages=[{"role": "user", "content": prompt}],
            max_retries=max_retries,
        )
        msg, lt, meta = str(res)[:30], LLMLogTypes.USAGE, com.dict()

    except Exception as e:
        res, com, msg, lt, meta = None, None, str(e), LLMLogTypes.ERROR, str(log_context)
        logger.warning(f"Error calling LLM: {e}")

    llm_call_log = LLMLog.objects.create(
        log_type=lt,
        session=log_context.pop("session", None),
        judgement=log_context.pop("judgement", None),
        step=log_context.pop("step", None),
        model=llm,
        message=msg,
        metadata=meta,
    )

    return res, com, llm_call_log


def simple_chat(prompt, llm, log_context={}):
    """For a text prompt and LLM model, return a string completion.

    Accepts log_context dictionary to pass to LLMLog creation on error.
    """

    # we can't use chat_with_completion because it needs a response model
    # so we return the first string completion, plus the completion object
    from mindframe.models import LLMLog, LLMLogTypes

    try:
        res = llm.provider.chat.completions.create(
            model=llm.model_name,
            response_model=None,
            messages=[{"role": "user", "content": prompt}],
        )
        res_text = res.choices[0].message.content
        res, com, msg, lt, meta = (
            res_text,
            res,
            res_text[:30] + "...",
            LLMLogTypes.USAGE,
            res.dict(),
        )

    except Exception as e:
        res, com, msg, lt, meta = None, None, str(e), LLMLogTypes.ERROR, str(log_context)
        logger.error(f"Error calling LLM: {e}")

    el = LLMLog.objects.create(
        log_type=lt,
        session=log_context.pop("session", None),
        judgement=log_context.pop("judgement", None),
        step=log_context.pop("step", None),
        model=llm,
        message=msg,
        metadata=meta,
    )
    logger.warning(f"MAKING llm log {el}")
    return res, com, el


class SpokenResponse(BaseModel):
    """A spoken response, continuing the previous conversation."""

    response: str = Field(
        ...,
        description="A spoken response, continuing the previous conversation. Don't label the speaker or use quotes, just the words spoken.",
    )


class PoeticalResponse(BaseModel):
    """A spoken response, continuing the previous conversation, in 16th C style."""

    response: str = Field(
        ...,
        description="A response, continuing the previous conversation but always in POETRICAL form - often a haiku.",
    )


class SelectionResponse(BaseModel):
    """A spoken response, continuing the previous conversation, in 16th C style."""

    response: str = Field(
        ...,
        description="A selection from one of the options. No discussion or explanation, just the text of the choice, exactly matching one of the options provided.",
    )


def chatter(multipart_prompt, model, log_context={}):
    """Split a prompt template into parts and iteratively complete each part, using previous prompts and completions as context for the next."""

    prompts_dict = split_multipart_prompt(multipart_prompt)
    results_dict = OrderedDict()

    prompt_parts = []
    llm_calls = []

    for key, value in prompts_dict.items():
        prompt_parts.append(value)
        prompt = "\n".join(prompt_parts)

        # we split the key on : to check if there is a special return type for this completion
        keyparts = re.split(r":\s?", key)

        if len(keyparts) == 1:
            # there is no specified return type, so we just
            # do the completion as simple chat
            key = keyparts[0]
            res, comp, log = simple_chat(prompt, model, log_context)
        else:
            # make sure we get a spoken response back
            # without other parts of the dialogue repeated

            # setup some special classes we can use in the prompt syntax
            # each class must at least have a `response` field which is extracted below
            resp_types = {
                "speak": SpokenResponse,
                "poem": PoeticalResponse,
                "pick": SelectionResponse,
            }
            return_type = resp_types.get(keyparts[0].strip(), SpokenResponse)
            key = keyparts[1].strip()

            res, comp, log = structured_chat(
                prompt + "\nAlways use the tools/JSON response.",
                model,
                return_type=return_type,
                log_context=log_context,
            )
            # extract the `response` field`
            res = res and res.response or None

        # check we have a string key to save the result, or make one from the prompt
        key = key or sha256(prompt.encode()).hexdigest()[:8]

        results_dict[key] = res
        prompt_parts.append(res)
        llm_calls.append(log)

    # duplicate the last item as the __RESPONSE__ so we have a
    # predictable key to access the final completion, but can still
    # also access the last key by names used in the template
    lastkey = next(reversed(results_dict))
    if lastkey != "__RESPONSE__":
        results_dict["__RESPONSE__"] = results_dict[lastkey]

    from mindframe.models import LLMLog

    return (results_dict, LLMLog.objects.filter(pk__in=[i.pk for i in llm_calls]))


# OLDER STUFF USING MAGENTIC


# @prompt("""{prompt}""")
# def chat(prompt: str) -> str: ...

# with AI_MODELS.cheap:
#     chat("say hello")

# def chatter_magentic(multipart_prompt, model=AI_MODELS.cheap):
#     """Split a prompt template into parts and iteratively complete each part, using previous prompts and completions as context for the next."""

#     prompts_dict = split_multipart_prompt(multipart_prompt)
#     results_dict = OrderedDict()

#     prompt_parts = []

#     for key, value in prompts_dict.items():
#         prompt_parts.append(value)
#         prompt = "\n".join(prompt_parts)
#         with model:
#             logger.debug(f"Calling LLM ({model}): {prompt[:60]} ...")
#             try:
#                 res = chat(prompt)
#                 results_dict[key] = ChatResult(
#                     value=res,
#                     prompt=prompt,
#                     input_tokens=len(encoding.encode(prompt)),
#                     output_tokens=len(encoding.encode(res)),
#                 )
#                 prompt_parts.append(res)
#             except Exception as e:
#                 logger.error(f"Error calling LLM: {e}")
#                 logger.error(f"Prompt: {prompt}")

#     # duplicate the last item as the __RESPONSE__ so we have a
#     # predictable key to access the final completion, but can still
#     # also access the last key by names used in the template
#     lastkey = next(reversed(results_dict))
#     if lastkey != "__RESPONSE__":
#         results_dict["__RESPONSE__"] = results_dict[lastkey]

#     return results_dict


# pmpt = """Think about mammals[[THOUGHTS]] Now tell me a joke[[JOKE]]"""
# results_dict = chatter(pmpt)
# results_dict.keys()
# results_dict['THOUGHTS']
# results_dict['__RESPONSE__'] == results_dict['JOKE']


# pmpt = """Think about mammals[[THOUGHTS]] Now tell me a joke"""
# results_dict = chatter(pmpt)
# list(results_dict.keys()) == ['THOUGHTS', '__RESPONSE__']
# results_dict['__RESPONSE__']
