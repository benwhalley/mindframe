CHUNKER_TEMPLATE = """
# Context 
This is a transcript of a conversation is broken into utterances, one per line.
So on each line you will see;

- the line number/ utterance id
- the speaker/interlocutor
- optionally, a timstamp
- the text of what was spoken


# The text to chunk

<-- start of source text -->

{source}

<-- end of source text -->

# Your task now

Split this conversation into chunks or 5-10 utterances
make the splits flexibly, but ideally break where the topic changes 
each chunk should be locally coherent
just return the utterance ids that separate the start and end of chunks as a list of lists
e.g. [[1,6], [5,12], ...]

It's ok to overlap the chunks to provide context - even by quite a bit.
Don't omit any of the utterances — everything must be included in at least 1 chunk.
Try to make sure the first utterance in each chunk makes it clear what subsequence utterances mean. I'd like to be able to read and use each chunk independently.

First think about the task and discuss where the chunks should be then, at the end, provide the list of list of ids.
Format the result with a full description of the chunk content and the start and end id. Make the chunk descriptions standalone — each should make it clear what is covered in the chunk without reference to other chunks or descriptions.

The ouptut should be in json format. It should include both the description and the id ranges like this.

## More explanation of the Chunking Task

The goal is to divide the conversation into coherent chunks, where each chunk can be understood as a standalone segment. We aim to break at natural topic transitions, ensuring that each chunk:

- Has local coherence: The topic within the chunk should be well-structured and clear.
- Provides context: Some overlap is allowed to make the start of each chunk self-explanatory.
- Reflects topic shifts: We break where there is a change in focus, such as shifting from general discussion about alcohol to specific health risks, goals, or coping strategies.

To split the conversation into coherent chunks, it's crucial to follow natural breaks in the dialogue and transitions between topics. Each chunk should include enough context for clarity while maintaining focus on specific themes or shifts in the discussion. I'll also ensure that each utterance is included in at least one chunk and provide descriptions that clearly encapsulate the content of each section.


# CHUNKED RESPONSE  [response in valid json only]

```json
[[chunked_conversation:]]
"""
