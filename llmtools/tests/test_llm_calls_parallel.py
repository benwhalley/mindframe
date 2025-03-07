import asyncio
import time
from pprint import pprint
from unittest import mock

from llmtools.llm_calling import chatter, chatter_
from mindframe.models import LLM


model = LLM.objects.get(model_name="gpt-4o-mini")

dependent_prompt = """
--
Fav season [[season]]
¡OBLIVIATE
Fav city [[city]]
¡OBLIVIATE
Describe {{city}} in {{season}} in a 10 line poem.
"""


dependent_prompt2 = """
--
Favorite season [[season]]
¡OBLIVIATE
Favorite city [[city]]
¡OBLIVIATE
Describe {{city}} in {{season}} in a 10 line poem.
"""


# Get a model instance for testing
model = LLM.objects.get(model_name="gpt-4o-mini")

# Test with patched structured_chat
# Time sequential execution (original chatter)
start_time = time.time()
sequential_result = chatter_(dependent_prompt, model, cache=False)
sequential_time = time.time() - start_time

# Time parallel execution (our new implementation)
start_time = time.time()
parallel_result = chatter(dependent_prompt2, model, cache=False)
parallel_time = time.time() - start_time


# Verify results are equivalent for independent segments
assert set(sequential_result.keys()) == set(parallel_result.keys()), "Keys don't match"

# Performance improvement assertions
speedup = sequential_time / parallel_time
print(f"\nSpeedup factor: {speedup:.2f}x")

# For independent segments, we expect significant speedup
# For 3 segments with 2 questions each, sequential takes ~12 sec, parallel ~4-6 sec
assert parallel_time < sequential_time, "Parallel should be faster for independent segments"

# For dependent segments, execution shouldn't be fully parallel but still optimized
assert (
    dependent_parallel_time <= sequential_time
), "Parallel should not be slower for dependent segments"

print(
    {
        "sequential_time": sequential_time,
        "parallel_time": parallel_time,
        "dependent_parallel_time": dependent_parallel_time,
        "speedup": speedup,
    }
)


# Expected output with 3 segments, 2 questions each:
# Sequential: ~12 seconds (6 API calls * 2 seconds each)
# Parallel independent: ~4-6 seconds (3 batches * 2 seconds each)
# Parallel dependent: ~8-10 seconds (depends on dependency graph)


mini = LLM.objects.filter(model_name="gpt-4o-mini").first()

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

tell me if this joke is funny
{{JOKE}}
[[JOKE_EVALUATION]]
"""

model = LLM.objects.get(model_name="gpt-4o-mini")
print(chatter(example_prompt, model))
print(chatter(example_prompt2, model))
