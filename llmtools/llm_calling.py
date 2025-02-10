"""
# Define your desired output structure

from pydantic import BaseModel, Field
from llmtools.llm_calling import structured_chat
from typing import Optional, List

from llmtools.llm_calling import *


smart = LLM.objects.get(model_name="gpt-4o")
mini = LLM.objects.get(model_name="gpt-4o-mini")



chatter("Think about mammals very briefly, in one or 2 lines: [[THOUGHTS]] Now tell me a joke. [[speak:JOKE]]", mini)[0]['JOKE']


convo = """ """
chunktmpl = """ """

chnks = chatter(chunktmpl.format(source=convo), model=smart)
chnks.response


for i in chnks.response:
    i.text= convo.split('\n')[i.start-1:i.end-1]["]
chnks



simple_chat

# this raises an exception
split_multipart_prompt("one[[]]two[[RESP]]dddd")

# tests
len(split_multipart_prompt("one[[x]]two[[RESP]]dddd").items())==3
split_multipart_prompt("one[[talk:y]]two[[RESP]]dddd")['talk:y'] == 'one'


rr = chatter("Pick an ancient civilisation: [[thoughts]] Now pick one of art, science or magic. Just one of those three words [[pick:topic]] Now tell me a SINGLE interesting fact[[speak:]]", mini)
rr.response
rr[1]

chatter("Think about mammals very briefly, in one or 2 lines: [[THOUGHTS]] Now tell me a joke. [[speak:JOKE]]", mini)[0]['JOKE']

chatter("Think about mammals very briefly, in one or 2 lines: [[THOUGHTS]] Now tell me a joke. [[poem:JOKE]]", mini)[0]['JOKE']

simple_chat("tell a joke", mini)[0]
simple_chat("tell a joke", local)[0]


zz = chatter("Think about mammals very briefly, in one or 2 lines: [[THOUGHTS]] Now tell me a joke[[JOKE]]", mini)
zz[0]

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

import traceback
import logging
import re
from collections import namedtuple, OrderedDict, defaultdict
from hashlib import sha256
from typing import List
from types import FunctionType
from django.apps import apps

from django.conf import settings
from django.template import Context, Template
from pydantic import BaseModel, Field
from llmtools.return_type_models import (
    SpokenResponse,
    InternalThoughtsResponse,
    selection_response_model,
    BooleanResponse,
    DefaultResponse,
    IntegerResponse,
    PoeticalResponse,
    ExtractedResponse,
    ChunkedConversationResponse,
)

from langfuse.decorators import observe
from langfuse.decorators import langfuse_context

langfuse_context.configure(debug=False)
from langfuse.openai import OpenAI  # OpenAI integration with tracing
from decouple import config

logger = logging.getLogger(__name__)

# a lookup dict of return types for different actions specified in prompt templates
ACTION_LOOKUP = defaultdict(lambda: DefaultResponse)
ACTION_LOOKUP.update(
    {
        "speak": SpokenResponse,
        "extract": ExtractedResponse,
        "think": InternalThoughtsResponse,
        "number": IntegerResponse,
        "int": IntegerResponse,
        "pick": selection_response_model,
        "decide": BooleanResponse,
        "boolean": BooleanResponse,
        "bool": BooleanResponse,
        "poem": PoeticalResponse,
        "chunked_conversation": ChunkedConversationResponse,
    }
)


def split_multipart_prompt(text) -> OrderedDict:
    """
    Split the prompt_template into an ordered dictionary of varname:prompt pairs.

    Templates are split wherever a `[[VARNAME]]` symbol occurs, defining a completion
    to be made by the llm.
    """

    # it is a bit gross to use regex
    # we should maybe use pandoc instead and traverse a tree nicely, see
    # import pandoc
    # from pandoc.types import *
    # alternately use pyparsing?
    # it works ok for now though...

    # some basic checks of template validity
    if bool(re.search(r"\[\[\s?\]\]", text)):
        raise Exception("Empty response key in prompt, e.g. [[]], is not allowed. Use [[var]].")
    # todo - check that:
    # - all var_names are valid python identifiers
    # - all actions are valid (i.e. can be found in ACTION_LOOKUP)

    varname_pattern = r"\[\[\s*([\w+\:\|\,\s+]+)\s*\]\]"
    parts = list(filter(bool, map(str.strip, re.split(varname_pattern, text))))
    # if we didn't explicitly include a final response variable, add one here
    if len(parts) % 2 == 1:
        parts.append("RESPONSE_")
    # iterate over tuples and return an ordered dictionary
    result = OrderedDict(zip(parts[1::2], parts[::2]))
    for text_segment, varname in zip(parts[::2], parts[1::2]):
        result[varname.strip()] = text_segment.strip()
    return result


# test1 = split_multipart_prompt("First part as aspeech[[pick:XXX|a,b,c]]second part as text[[yyy]]")
# list(test1.keys())[0] == "pick:XXX|a,b,c"
# list(test1.keys())[1] == "yyy"


def extract_keys_and_options(key):
    """
    Returns the keyname and return type and response options as a KeyParts namedtuple.

    Args:
        key (str): A string like "returntype:keyname|option1,option2,option3" or "keymame"

    Returns:
        namedtuple: KeyParts, with name, return_type and return_options fields.

    Examples:

        >>> extract_keys_and_options("action:VAR_NAME|option1,option2,option3")

    """
    # split on colon
    keyparts = re.split(r":\s?", key)
    if len(keyparts) == 1:
        kn_ops = keyparts[0].strip()
        rn = None
    else:
        kn_ops = keyparts[1].strip()
        rn = keyparts[0].strip()
    # split the kn and options on the pipe (|) symbol
    kn_ops_split = re.split(r"\|\s?", kn_ops)
    kn = kn_ops_split[0].strip()
    if len(kn_ops_split) == 1:
        ro = None
    else:
        ro = [i.strip() for i in kn_ops_split[1].strip().split(",")]

    return namedtuple("KeyParts", ["name", "return_type", "return_options"])(
        kn, ACTION_LOOKUP[rn], ro
    )


def parse_prompt(prompt_text) -> OrderedDict:
    '''
    Parse a multi-part prompt into an ordered dictionary of key-value pairs.

    Each key is the variable name, and the value is a `PromptPart` object containing:
    - `key`: the variable name.
    - `return_type`: the action and so return value specified in the prompt (e.g., "speak", "pick").
    - `options`: any options specified in the prompt (e.g., "a,b,c").
    - `text`: the corresponding text from the prompt.

    Args:
        prompt_text (str): A string containing the multi-part prompt.

    Returns:
        OrderedDict: An ordered dictionary where keys are variable names, and values are `PromptPart` objects.

    Notes:
        - If no explicit key is provided, a hash of the prompt text is used as the key.

    Examples:
        >>> def split_multipart_prompt(prompt_text):
        ...     # Example helper to split prompts for testing
        ...     return OrderedDict({
        ...         "speak:A": "A is spoken",
        ...         "B": "B is spoken",
        ...         "pick:C|a,b,c": "C is chosen",
        ...         "think:D": "D is a thought"
        ...     })
        >>> def extract_keys_and_options(key_text):
        ...     # Example helper to extract keys and options
        ...     key, _, options = key_text.partition("|")
        ...     return namedtuple("KeyPart", ["name", "return_type", "return_options"])(*key.split(":"), options.split(",") if options else [])
        >>> test2 = parse_prompt("""
        ... A is spoken [[speak:A]]
        ... B is spoken [[B]]
        ... C is chosen [[pick:C|a,b,c]]
        ... D is a thought [[think:D]]
        ... """)
        >>> test2[0].key == "A"


    TODO:  additional tests needed so that:
    - options can only be specified for `pick` actions
    - a key must be specified, or is returned as the hash of the prompt text so we always have a key
    - others...
    '''

    pro_dic = split_multipart_prompt(prompt_text)
    parts = [(extract_keys_and_options(k), v) for k, v in pro_dic.items()]

    return OrderedDict(
        {
            k.name: namedtuple("PromptPart", ["key", "return_type", "options", "text"])(
                k.name, k.return_type, k.return_options, v
            )
            for k, v in parts
        }
    )


@observe(capture_input=False, capture_output=False)
def structured_chat(
    prompt,
    llm,
    return_type,
    max_retries=3,
    log_context={},
):
    """
    Make a tool call to an LLM, returning the `response` field, a completion object and the LLMLog.
    """

    langfuse_context.update_current_observation(input=prompt)

    try:
        res, com = llm.client.chat.completions.create_with_completion(
            model=llm.model_name,
            response_model=return_type,
            messages=[{"role": "user", "content": prompt}],
            max_retries=max_retries,
        )
        msg, lt, meta = res.response, None, com.dict()

    except Exception as e:
        # res, com, msg, lt, meta = None, None, str(e), LLMLogTypes.ERROR, str(log_context)
        full_traceback = traceback.format_exc()
        logger.warning(f"Error calling LLM: {e}\n{full_traceback}")

    llm_call_log = None
    # LLMLog.objects.create(
    #     variable_name=log_context.get("variable_name", "?"),
    #     log_type=lt,
    #     session=log_context.get("session", None),
    #     judgement=log_context.get("judgement", None),
    #     turn=log_context.get("turn", None),
    #     step=log_context.get("step", None),
    #     model=llm,
    #     message=msg,
    #     prompt_text=prompt,
    #     metadata=meta,
    # )

    return res, com, llm_call_log


@observe(capture_input=False, capture_output=False)
def simple_chat(prompt, llm, log_context={}):
    """For a text prompt and LLM model, return a string completion.

    Accepts log_context dictionary to pass to LLMLog creation on error.
    """

    # we can't use chat_with_completion because it needs a response model
    # so we return the first string completion, plus the completion object
    # from mindframe.models import LLMLog, LLMLogTypes

    langfuse_context.update_current_observation(input=prompt)

    try:
        res = llm.client.chat.completions.create(
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
        # res, com, msg, lt, meta = None, None, str(e), LLMLogTypes.ERROR, str(log_context)
        logger.error(f"Error calling LLM: {e}")

    el = None
    # LLMLog.objects.create(
    #     variable_name=log_context.get("variable_name", None),
    #     log_type=lt,
    #     session=log_context.get("session", None),
    #     judgement=log_context.get("judgement", None),
    #     turn=log_context.get("turn", None),
    #     step=log_context.get("step", None),
    #     model=llm,
    #     message=msg,
    #     prompt_text=prompt,
    #     metadata=meta,
    # )
    logger.warning(f"MAKING llm log {el}")
    return res, com, el


# prefix attached to all prompts to ensure templating syntax works
TEMPLATE_PREFIX = """
{% load pretty %}
{% load guidance %}
{% load rag %}
{% load turns %}
{% load examples %}
{% load notes %}
"""


class ChatterResult(OrderedDict):
    @property
    def response(self):
        # return the RESPONSE_ or last item in the dict
        return self["RESPONSE_"] or next(reversed(self.items()))[1]


@observe(capture_input=False, capture_output=False)
def chatter(multipart_prompt, model, context={}, log_context={}):
    """
    Split a prompt template into parts and iteratively complete each part, using previous prompts and completions as context for the next.

    If the prompt contains a segment break (by default, any occurrence of "|||===..."
    i.e. three or more "=" following "|||"), the prompt is split into segments.
    Each segment is processed separately. For segments after the break, previous
    completions are not automatically appended to the prompt text; however, any
    desired value from a previous segment can be injected via the template's
    double-curly syntax (e.g. {{VAR}}).

    The completions from earlier segments are accumulated into a context dictionary,
    making them available for explicit use in later segments.
    """
    # Define a regex to split the prompt into segments.
    # e.g. |||=== or ||| ===
    SEGMENT_SPLIT_RE = re.compile(r"\|\|\|\s*={3,}\s*")

    final_results = ChatterResult()
    # This dict will accumulate all completions across segments,
    # so that later segments can reference earlier outputs using {{key}}.
    accumulated_context = {}

    # Split the entire prompt by the segment break marker.
    segments = SEGMENT_SPLIT_RE.split(multipart_prompt)

    # If no segment break is found, segments will be a list with one element.
    for segment in segments:
        # Process the current segment using the normal multipart parser.
        pprompt = parse_prompt(segment)
        # In a segmented prompt, we do not want to automatically include the
        # results from previous segments into the prompt text. Instead, we let
        # the author decide which earlier outputs to reference via template vars.
        prompt_parts = []

        for key, prompt_part in pprompt.items():
            # Append the raw text for this prompt part.
            prompt_parts.append(prompt_part.text)
            # Build the prompt for this completion from the parts within this segment.
            segment_prompt = "\n\n--\n\n".join(prompt_parts)

            # Merge the provided context with the accumulated completions
            # so that any template variable like {{JOKE}} gets replaced.
            merged_context = context.copy()
            merged_context.update(accumulated_context)

            # Render the prompt template.
            template = Template(
                TEMPLATE_PREFIX
                + segment_prompt
                + "\nAlways use the tools/JSON response.\n\n```json\n"
            )
            rendered_prompt = template.render(Context(merged_context))

            # Determine the appropriate return type.
            if isinstance(prompt_part.return_type, FunctionType):
                rt = prompt_part.return_type(prompt_part.options)
            else:
                rt = prompt_part.return_type

            # Call the LLM via structured_chat.
            res, completion_obj, log = structured_chat(
                rendered_prompt, model, return_type=rt, log_context=log_context
            )
            res = res and res.response or None
            log_context["variable_name"] = key

            if key in ["RESPONSE_", "response"]:
                logging.info(f"\033[32mCompletion: {key}\n{res}\n\033[0m")
            else:
                logging.info(f"Completion: {key}\n{res}\n")

            # Store the completion in both our final results and accumulated context.
            final_results[key] = res
            accumulated_context[key] = res

            # For this segment, include the result in the prompt parts if desired.
            # This preserves the original behaviour within a segment.
            prompt_parts.append(res)

        # If the segment didn't explicitly yield a key "RESPONSE_", set it to the last result.
        last_key = next(reversed(final_results))
        if last_key != "RESPONSE_":
            final_results["RESPONSE_"] = final_results[last_key]

    return final_results


def get_embedding(texts, dimensions=1024) -> list:
    """

    get_embedding(["gello"])

    """
    client = OpenAI(api_key=config("LITELLM_API_KEY"), base_url=config("LITELLM_ENDPOINT"))
    response = client.embeddings.create(
        input=texts,
        model="text-embedding-3-large",
        dimensions=dimensions,
    )
    return [i.embedding for i in response.data]


if False:
    from pprint import pprint
    from mindframe.models import LLM
    from llmtools.llm_calling import chatter, parse_prompt

    mini = LLM.objects.filter(provider_name="AZURE", model_name="gpt-4o-mini").first()

    t4 = chatter(
        """
    Say something funny [[speak:A]]
    And another thing: [[B]]
    How funny are you? Pick one of the following: [[pick:C|unfunny, abitfunny, veryfunny]]

    Think about this chat session. What is happening here? [[think:D]]
    """,
        model=mini,
    )
    t4

    t5 = chatter(
        """
    Tell a joke [[speak:A]]
    Think about this chat session. What is happening here? [[think:D]]
    Is this a real conversation [[pick:E|yes, no]]
    """,
        model=mini,
    )
    t5

    chatter(
        """
    Think about mammals: [[think:D]]
    """,
        model=mini,
    )

    # examples of segmenting a prompt

    example_prompt = """
    tell me a joke about apples
    [[JOKE]]
    tell me if the {{JOKE}} is funny
    [[JOKE_EVALUATION]]
    """

    example_prompt2 = """
    tell me a joke about apples
    [[JOKE]]

    |||===

    tell me if the {{JOKE}} is funny
    [[JOKE_EVALUATION]]
    """

    model = LLM.objects.get(model_name="gpt-4o-mini")
    print(chatter(example_prompt, model))
    print(chatter(example_prompt2, model))
