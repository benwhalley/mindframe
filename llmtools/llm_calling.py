import asyncio
import hashlib
import io
import logging
import re
import traceback
from collections import OrderedDict, namedtuple
from hashlib import sha256
from types import FunctionType
from typing import Any, Dict, List
from box import Box
import requests
from asgiref.sync import async_to_sync, sync_to_async
from colored import Back, Fore, Style
from django.template import Context, Template
from langfuse.decorators import langfuse_context, observe
from pydantic import Field
from pydub import AudioSegment

from llmtools.return_type_models import ACTION_LOOKUP

langfuse_context.configure(debug=False)
from decouple import config
from langfuse.openai import OpenAI  # OpenAI integration with tracing

logger = logging.getLogger(__name__)

# a lookup dict of return types for different actions specified in prompt templates


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

    # extract [[response]] blocks with regex
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

    valops = namedtuple("KeyParts", ["name", "return_type", "return_options"])(
        kn, ACTION_LOOKUP[rn], ro
    )
    logger.info(f"Extracted options: {valops}")
    return valops


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
def structured_chat(prompt, llm, return_type, max_retries=3, extra_body={}):
    """
    Make a tool call to an LLM, returning the `response` field, and a completion object
    """

    langfuse_context.update_current_observation(input=prompt)
    try:
        res, com = llm.client.chat.completions.create_with_completion(
            model=llm.model_name,
            response_model=return_type,
            messages=[{"role": "user", "content": prompt}],
            max_retries=max_retries,
            extra_body=extra_body,
        )
        msg, lt, meta = res, None, com.dict()

    except Exception as e:
        full_traceback = traceback.format_exc()
        logger.warning(f"Error calling LLM: {e}\n{full_traceback}")
        res, com = None, None

    return res, com


@observe(capture_input=False, capture_output=False)
def simple_chat(prompt, llm, extra_body={}):
    """For a text prompt and LLM model, return a string completion."""

    # we can't use chat_with_completion because it needs a response model
    # so we return the first string completion, plus the completion object

    langfuse_context.update_current_observation(input=prompt)

    try:
        res = llm.client.chat.completions.create(
            model=llm.model_name,
            response_model=None,
            messages=[{"role": "user", "content": prompt}],
            extra_body=extra_body,
        )
        res_text = res.choices[0].message.content
        res, com = (
            res_text,
            res,
        )

    except Exception as e:
        logger.error(f"Error calling LLM: {e}")

    return res, com


# prefix attached to all prompt text/templates to ensure templating syntax works
TEMPLATE_PREFIX = """
{% load pretty %}
{% load guidance %}
{% load rag %}
{% load turns %}
{% load notes %}
"""


class ChatterResult(OrderedDict):
    @property
    def response(self):
        # return the RESPONSE_ or last item in the dict
        return self["RESPONSE_"] or next(reversed(self.items()))[1]

    @property
    def outputs(self):
        return Box(self)


@observe(capture_input=False, capture_output=False)
def chatter_(multipart_prompt, model, context={}, cache=True):
    """
    Split a prompt template into parts and iteratively complete each part, using previous prompts and completions as context for the next.

    If the prompt contains a segment break (by default, any occurrence of "¡OBLIVIATE"
    i.e. inverted exclamation mark + the word "OBLIVIATE", then the prompt is split into segments.
    Each segment is processed separately. For segments after the spell, previous
    completions are NOT automatically included in the prompt text as they normally would be; however, any desired value from a previous segment can be injected via the template's double-curly syntax (e.g. {{VAR}}).

    The completions from earlier segments are accumulated into a context dictionary,
    making them available for explicit use in later segments.
    """

    # litellm takes a cache param in extra_body, see
    # https://docs.litellm.ai/docs/proxy/caching
    # ttl	Optional(int)	Will cache the response for the user-defined amount of time (in seconds)
    # s-maxage	Optional(int)	Will only accept cached responses that are within user-defined range (in seconds)
    # no-cache	Optional(bool)	Will not store the response in cache.
    # no-store	Optional(bool)	Will not cache the response
    # namespace	Optional(str)	Will cache the response under a user-defined namespace

    if not cache:
        extra_body = {"cache": {"no-store": True}}
    else:
        extra_body = {}

    # Define a regex to split the prompt into segments.
    # e.g. |||=== or ||| ===
    SEGMENT_SPLIT_RE = re.compile(r"¡OBLIVIATE\s*")

    logger.warning("ENTIRE PROMPT\n\n")
    logger.warning(multipart_prompt + "\n\n\n")

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

        logger.info("PPROMPT", pprompt)

        for key, prompt_part in pprompt.items():
            # Append the raw text for this prompt part.
            prompt_parts.append(prompt_part.text)
            # Build the prompt for this completion from the parts within this segment.
            try:
                segment_prompt = "\n\n--\n\n".join(filter(bool, map(str, prompt_parts)))
            except Exception as e:
                logger.error(f"Error building segment prompt: {prompt_parts}\n{e}")

            # Merge the provided context with the accumulated completions
            # so that any template variable like {{JOKE}} gets replaced.
            merged_context = context and context.copy() or {}
            merged_context.update(accumulated_context)

            # Render the prompt template.
            template = Template(
                TEMPLATE_PREFIX
                + segment_prompt
                + "\nAlways use the tools/JSON response.\n\n```json\n"
            )
            rendered_prompt = template.render(Context(merged_context))
            logger.info(f"{Fore.cyan}{rendered_prompt}{Style.reset}")
            # Determine the appropriate return type.
            if isinstance(prompt_part.return_type, FunctionType):
                rt = prompt_part.return_type(prompt_part.options)
            else:
                rt = prompt_part.return_type

            # Call the LLM via structured_chat.
            res, completion_obj = structured_chat(
                rendered_prompt, model, return_type=rt, extra_body=extra_body
            )
            res = res and res.response or None

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


# Asyncronos version of chatter_ which allows for parallel processing of segments
# Segments are identified by the ¡OBLIVIATE marker at the moment


class ParallelSegmentResult:
    """Class to hold results from a parallel segment execution"""

    def __init__(self, segment_id, completions, dependencies=None):
        self.segment_id = segment_id
        self.completions = completions  # Dict of key -> completion
        self.dependencies = dependencies or set()  # Set of segment_ids this segment depends on


class SegmentDependencyGraph:
    """Analyzes dependencies between segments and determines execution order"""

    def __init__(self, segments: List[str]):
        self.segments = segments
        self.dependency_graph = {}  # segment_id -> set of segment_ids it depends on
        self.segment_vars = {}  # segment_id -> set of variable names defined in this segment
        self.build_dependency_graph()

    def build_dependency_graph(self):
        # First pass: identify variables defined in each segment
        for i, segment in enumerate(self.segments):
            segment_id = f"segment_{i}"
            # Extract variable names from prompt segment
            pprompt = parse_prompt(segment)
            self.segment_vars[segment_id] = set(pprompt.keys())
            self.dependency_graph[segment_id] = set()

        # Second pass: identify dependencies between segments
        for i, segment in enumerate(self.segments):
            segment_id = f"segment_{i}"
            # Find all template variables {{ VAR}} in the segment
            template_vars = set(re.findall(r"\{\{\s*(\w+)\s*\}\}", segment))

            # For each template variable, find which earlier segment defines it
            for var in template_vars:
                for j in range(i):
                    dep_segment_id = f"segment_{j}"
                    if var in self.segment_vars[dep_segment_id]:
                        self.dependency_graph[segment_id].add(dep_segment_id)

    def get_execution_plan(self) -> List[List[str]]:
        """
        Returns a list of batches, where each batch is a list of segment_ids
        that can be executed in parallel
        """
        remaining = set(self.dependency_graph.keys())
        execution_plan = []

        while remaining:
            # segments with no unprocessed dependencies
            ready = {
                seg_id
                for seg_id in remaining
                if all(dep not in remaining for dep in self.dependency_graph[seg_id])
            }

            if not ready and remaining:
                # Circular dependency detected
                logging.warning(f"Circular dependency detected in segments: {remaining}")
                # Fall back to sequential execution for remaining segments
                execution_plan.extend([[seg_id] for seg_id in remaining])
                break

            execution_plan.append(list(ready))
            remaining -= ready

        return execution_plan


async def chatter_async(multipart_prompt: str, model, context={}, cache=True) -> ChatterResult:
    """
    Parallel version of chatter that processes independent segments concurrently.

    For example, if we have

    ```
    Fav fruit? [[fruit]]
    !OBLIVIATE
    Fav color? [[color]]
    !OBLIVIATE
    Tell me a story about a {{color}} {{fruit}}
    [[story]]
    ```

    `fruit` and `color` are processed in parallel.
    The final segment is processed after both are complete.

    """
    # Use original chatter for single-segment prompts
    segments = re.compile(r"¡OBLIVIATE\s*").split(multipart_prompt)

    # Analyze dependencies between segments
    dependency_graph = SegmentDependencyGraph(segments)
    execution_plan = dependency_graph.get_execution_plan()
    print(execution_plan)

    # Final results and accumulated context
    final_results = ChatterResult()
    accumulated_context = context.copy()

    # Process each batch in the execution plan sequentially
    for batch in execution_plan:
        segment_tasks = []

        # Start tasks for all segments in this batch
        for segment_id in batch:
            segment_index = int(segment_id.split("_")[1])
            segment = segments[segment_index]

            # Use sync_to_async to safely call chatter from async context
            task = sync_to_async(chatter_, thread_sensitive=True)(
                segment, model, accumulated_context, cache
            )
            segment_tasks.append(task)

        # Wait for all segments in this batch to complete
        batch_results = await asyncio.gather(*segment_tasks)

        # Add results to accumulated context for next batch
        for i, result in enumerate(batch_results):
            accumulated_context.update(dict(result))
            final_results.update(dict(result))

    # Set RESPONSE_ if needed
    if "RESPONSE_" not in final_results and final_results:
        last_key = next(reversed(final_results))
        final_results["RESPONSE_"] = final_results[last_key]

    return final_results


def chatter(multipart_prompt: str, model, context={}, cache=True) -> ChatterResult:
    """Synchronous wrapper for chatter_async"""
    return async_to_sync(chatter_async)(multipart_prompt, model, context, cache)


from moviepy import VideoFileClip


def convert_audio(input_bytes, to="mp3"):
    input_audio = AudioSegment.from_file(io.BytesIO(input_bytes))
    output_buffer = io.BytesIO()
    input_audio.export(output_buffer, format=to)
    output_buffer.seek(0)
    return output_buffer


def get_source_bytes_(source: str) -> bytes:
    # Check if audio_source is a URL or file
    if source.startswith("http://") or source.startswith("https://"):
        response = requests.get(source)
        if response.status_code == 200:
            content = response.content
        else:
            logger.error(f"Failed to download audio from URL: {source}")
            return ""
    else:
        # Assume it is a file path
        with open(audio_source, "rb") as file:
            content = file.read()

    return content


def whisper_transcribe_audio_(audio_input, language: str = "en") -> str:
    client = OpenAI(api_key=config("LITELLM_API_KEY"), base_url=config("LITELLM_ENDPOINT"))

    # Check if audio_input is a byte stream or file path
    if isinstance(audio_input, bytes):
        audio_file = io.BytesIO(audio_input)
        # Whisper requires a filename
        audio_file.name = f"{hashlib.sha256(audio_input).hexdigest()}.mp3"
    elif isinstance(audio_input, str):
        audio_file = open(audio_input, "rb")
    else:
        raise ValueError("Invalid audio input: must be bytes or file path.")

    try:
        response = client.audio.transcriptions.create(
            file=audio_file, model="whisper", language=language
        )
        return response.text
    finally:
        if hasattr(audio_file, "close"):
            audio_file.close()


def transcribe_audio(source: str, language: str = "en") -> str:
    """
    Transcribe audio or video using Whisper from Azure OpenAI.

    Args:
        source (str): Path to the audio/video file or URL of the media.
        language (str): Language code for transcription (default: English).

    Returns:
        str: Transcribed text from the audio or video.
    """
    try:
        content = get_source_bytes_(source)
        audio_bytes = convert_audio(content, to="mp3")

    except Exception as e:
        logger.error(f"Error converting source to audio: {e}")
        return ""

    try:
        return whisper_transcribe_audio_(audio_bytes.read(), language)
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        return ""
