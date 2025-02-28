# A taxonomy of prompt styles for conversational therapy AI

-   Role
-   Orientation/Instruction
-   Context
-   Format: Guidance/instructions given
-   Continuation: the prompt implicitly demands a continuation.
-   Response: the prompt explicitly asks for a response.

We should also consider:

-   Constraints: the LLM API provides options to constrain the possible responses, e.g. to require that responses conform to a typed schema (most often, to provide JSON which corresponds to a specific structure and that could be passed to a function with typed arguments).

## LLM prompt structures

In multi-turn systems, we can distinguish two approaches to building a prompt to the LLM:

-   Concatenating
-   Templated


#### Context, Continuation

This is one of the simplest possible structures.

Imagine pasting a conversation transcript into ChatGPT's web interface, and continuing the conversation in repeated turns.

```
[therapist] hi, how are are you today?
not feeling so good
⨁
```

Here, the ⨁ symbol indicates a place at which the prompt ends and response is made by the LLM. In this instance the content of the continuation is implied by the structure of the conversation so far and is not explcitly stated.

Given this prompt, ChatGPT-4o responds with the completion:

> [therapist] I'm sorry to hear that. Do you want to talk about what's been going on?


And, if the user then continues the conversation with "not really" the model responds with:

> [therapist] That's okay. I'm here if you change your mind. Would you like to do something to take your mind off things for a bit?


It's perhaps obvious, but worth emphasising that most current LLM APIs are stateless, and don't preserve execution state between completions (sometimes cacheing layers provided as part of the API might make it seem as though the model is stateful, but this is not the case).

When the model makes the final response, it is to a single prompt that is equivalent to all previous prompts and answers concatenated together:

```
[therapist] hi, how are are you today?
not feeling so good
[therapist] I'm sorry to hear that. Do you want to talk about what's been going on?
not really
⨁
```



#### Instruction, Context, Continuation

A common extension this approach is to include instructions or a role or persona definiton *before* the conversation context:

```
You are an expert therapist.  Always be kind when you speak.

[therapist] hi, how are are you today

not feeling so good

[therapist] ⨁
```

In this example, subsequent turns are again concatenated, and the total length of the prompt builds over time.

However, because LLMs are stateless there is no necessity that the previous conversation history is included at the *end* of the prompt.

Instead, we can *template* our prompts, keeping track of instructions, context and responses sepatately and building a fresh prompt each time.

### Templated responses

Users do not interact with LLMs directly.  Although not always obvious in use, interfaces to LLMs are stateful, can maintain a conversation history, and use this structure to generate prompts which are fed to the underlying model. It's important to remember that the user does not actually see the prompt that is fed to the model, but only i) the representation of it provided by the user interface and ii) the response that is generated (or a transformation of it).

This means that even though it might look to the user that their conversation is produced by a concatenative process this is not _necessarily_ the case. In reality, the system is likely to be templating the conversation history, instructions, context and responses together to generate a fresh prompt each time.

In the context of conversational agents for therapy, this templating process is likely to be more complex than in other applications, because the system needs to keep track of the therapist's persona, the goals of the conversation, and the structure of the conversation so far.


#### Context, Instruction, Response

A simple templated prompt is below:
```
[therapist] hi, how are are you today
[client] not feeling so good
                [turns omitted]

Pretend to be a therapist. Continue this
conversation with the client.

⨁
```

The form here is:

```
{context}
{instruction}
⨁
```


In practice, templates like this are often amended slightly to include _cues_ to the model about the desired response. For example, adding the speaker name in square brackets before the end of prompt emphasises to the model that
- it should simulate the therapist utterance
- it is not necessry to include the speaker name in the response (because it is already in the prompt)


In the first example, the model responds:

> [therapist] I’m sorry to hear that. Want to tell me a bit about what’s going on?

And in the second, it responds:

> I’m sorry to hear that. Want to tell me a bit about what’s going on?



The important point here is that:


- it's not required that the previous 'turns' (user input)  be concatenated at the end of the prompt

- models are sensitive to cues in the prompt about the nature of the desired output

- the structure of the prompt can be used to guide the model's output



#### Authorial control of prompt structures

Given this, we can imagine a wide range of prompt structures including roles, instructions, context, guidance and formatting instructions.

```
You are an excellent therapist.
This is your conversation so far. Read carefully.

[therapist] hi, how are are you today
[client] not feeling so good
...                [turns omitted]

Follow the principles of CBT.
Open questions help the client express themselves.
Use reflections to show you are listening.
[therapist]: ⨁
```




#### Chain of thought prompts


```
You are an excellent therapist.
This is your conversation so far. Read carefully.

[therapist] hi, how are are you today
[client] not feeling so good
...                [turns omitted]

Follow the principles of CBT.
Open questions help the client express themselves.
Use reflections to show you are listening.

Think carefully. What could the therapist do at this point?

Ⓐ
```

The problem here is that


One workaround is to request a response format in which different components of the answer can be parsed by the user interface and stored and displayed separately.

For example,  it's common to append the instruction to respond in JSON format:

```
[previous chain of thought prompt]

Respond in this format:

{
    'thoughts': '<your thoughts here>',
    'response': '<what the therapist said next>'
}

Ⓐ
```


#### Multipart prompting or prompt-chaining

Alternatively, to encourage chain of thought responses whilst also solving the problem of the model not being able to generate multiple responses in a single turn, we can use a multipart prompt. That is, two prompts which run sequentially, and where the ouput from the first is available as input to the second.

Prompt 1:

```
You are an excellent therapist.
This is your conversation so far. Read carefully.

[therapist] hi, how are are you today
[client] not feeling so good
...                [turns omitted]

Follow the principles of CBT.
Open questions help the client express themselves.
Use reflections to show you are listening.

Think carefully. What could the therapist do at this point?
⨁
```


In a second prompt, we can ask the model to continue the conversation:

```
You are an excellent therapist.
This is your conversation so far.

[therapist] hi, how are are you today
[client] not feeling so good

You have decided a good course of action is to:
{response to prompt 1}

Continue the conversation as the therapist.
[therapist]: ⨁
```


In sophisticated implementations, the controller system can rquest multiple completions in paralell and combine inputs into a single prompt which generates a final response. This is a powerful way to generate complex, multi-turn conversations with the model.


```{mermaid}
Input -> Prompt A
Input -> Prompt B
Response A -> Prompt C
Response B -> Prompt C
```


Prompt A might be:

```
{context}
What emotional state is this client in?
⨁
```

Prompt B might be:

```
{context}
Read this conversation.What is the client's primary worry?
⨁
```

Prompt C might be:

```
{context}
The client is feeling: {response A}
The client's primary worry is: {response B}
⨁
```

The response made in C is returned to the user.



### Challenges for treatment developers

The problem with this approach is that treatment developers are typically non-technical users and may not be able to easily create these complex prompt structures using current software (e.g. langchain).

Mindframe attempts to provide simple solutions to the most common prompting patterns, and good default patterns for psychological interventions.


## Empirical questions: which prompt structures are most effective?

Given the list of components (role, orientation, context, format, continuation, response) we can ask which of these are most effective in generating good quality responses from the model?

The existing literature is not clear on this point, and papers often fail to report prompts in detail, or how they were templated.
