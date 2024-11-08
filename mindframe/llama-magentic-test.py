from magentic import prompt
from magentic.chat_model.litellm_chat_model import LitellmChatModel
from pydantic import BaseModel
from typing import List


local = LitellmChatModel("ollama/llama3.2", api_base="http://localhost:11434")


class StoryModel(BaseModel):
    number: int
    story: str


class NestedStoryModel(BaseModel):
    stories: List[StoryModel]


@prompt(
    """Pick a random number less than {n} and  tell me a story about it. 
    Respond in JSON in the format specified."""
)
def story(n: int) -> StoryModel: ...


# this works with local and openai models
with local:
    print(story(10))


@prompt(
    """Pick a random number less than {n} and  tell me a story about it. 
    Do this {k} times and return a list of stories.
    Respond in JSON in the format specified.
    """
)
def storylist(n: int, k: int) -> NestedStoryModel: ...


# this only works with openai, and not ollama

# with openai:
print(storylist(10, 3))

with local:
    print(storylist(10, 3))
