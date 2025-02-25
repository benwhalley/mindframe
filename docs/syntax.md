
# Mindframe prompting syntax


## TLDR

Prompts are written in plain text/markdown, with some additional
tags for dynamic content, like conversation history or extracted data.

An example prompt for a step:

```
You are an expert in behaviour change.
You and the client are working on {{data.problem.summary}}.

These are some examples which might be relevant:
{% examples data.problem.summary %}

This is your professional formualtion of the case so far:
{{data.formulation}}

This is what has been said recently (last N turns of the conversation):
{% turns 'all' n=30 %}

Think about what you would say next. Consider all perspectives:
[[think:approach]]

Now, say something to the client. Keep it simple.
[[speak:response]]

```


And for a Judgement with the variable name `step_judgement`:

```
You are a clinical psychologist working
with a client on {{data.problem}}.

This is a summary of what has been said so far:
{{data.step_judgement.summary|default:"No summary available"}}


This is the most recent conversation between you and the client:
{% turns 'all' n=10 %}

Update the conversation summary with any new information:

[[summary]]


Does the client show willingness to engage in treatment:

[[pick:willingness|yes,no,unclear]]

Is the client displaying risky behaviour or threatening self-harm?

[[boolean:risk]]

```


Notice that multiple responses can be requested from the AI, using `[[response]]` tags. Details of the different prefixes for responsess (like `pick` and `boolean`) are explained below.



# Detailed syntax guide

Prompts for steps and judgements are written in a simple markdown format,
with some additional tags for dynamic content.

### `turns`: including conversation history

This includes the whole conversation so far (screenplay format):

```
{% turns 'all' %}
```

Everything said in this step

```
{% turns 'step' %}
```

Last 2 things said:

```
{% turns 'step' n=2 %}
```



### Notes: data extracted from the conversation:

Notes made from previous judgements can be included in the template, using the `data` variable.

For example, if we had a Judgement which extracted and saved the client's name, we can in include it in the template:

```
You are working with {{data.preferred_name.name}}.
```


E.g. a Judgement identifies a 'problem' we want to work on:

```
{{data.problem_identified.problem}}
```


Or we use a Judgement to make a clinical summary of conversation in previous steps.
Here the Judgement variable name is `step_summary`, and the
response that we want to use is called `summary`:

```
{{data.step_summary.summary}}
```



### Requesting AI responses

As part of a template, we can ask the AI to respond multiple times.
Each time we want a response, we include a `[[RESPONSE]]` tag:
At minimum, two square braces surrounding a variable name.

Example of a two-part response:

```
Consider the whole conversation so far.
Formulate a response to the client's concerns.
Consider both systemic and individual factors.

[[formulation]]

Now, think about what to say next.
You can only say one thing. Keep it simple

[[therapist_response]]
```


Optionally, a prefix can be used to guide the style of the AI response.
Presently `think` and `speak` are supported, but more may be added:

```
[[think:response]]
[[speak:response]]
```

A `think` response is more reflective, longer, and can include notes/plans.
The `speak` response is more direct an the AI is requested to use spoken idioms.
These different styles of responses are achieved by adding hints to the call to the AI model.


### Classification responses

Two other prefixes are also supported to allow for classification responses:

```
[[boolean:response]]

[[pick:response|option1, option2, option3, default=null]]

```

Or, a multiline version:

```
[[pick:response
    option1
    option2
    option3
    default=null]]
```


- `pick` guarantees that the response is one of the options provided, after the `|` character, separated by commas.
- `boolean` guarantees that the response is either True or False.

These are useful when making classifications, or for Judgements that determine whether a
step transition should take place.

Finally, advanced users can pass extra parameters to `[[response]]` slots, using the following syntax:

```
[[think:planning]]{max_tokens=50}

[[bool:is_upset]]{allow_null=true}
```




## Using RAG: including examples of good practice

NOTE - SYNTAX FOR RAG IS CHANGING AND INCLUDING EXAMPLES ARE CURRENTLY NOT IMPLEMENTED

Examples of good practice on a topic for a given scenario:

```
{% examples 'reflection' %}
{% examples 'a client finding it hard to generate imagery' %}
```


Examples of good practice relevant to something a client said (i.e. dynamically found and included):

```
{% examples data.problem_elicited %}
```


## Comments in templates

TODO: Implement this.

```
\\ This is a comment and won't be visible to the AI model
You are an AI therapist.
Help the client with their problem.
[[speak:response]]

```




## Saving tokens with `OBLIVIATE!`

Sometimes, we want to:

A. use an initial prompt to create a response
B. refine the response, using secondary instructions


In part A, we provide the LLM a lot of context.
In part B, we may not need all this context.

To save tokens, we can take the response from part A, and use it as input for part B.
This is done with the `¡OBLIVIATE` tag.

Example:

```
Long context about the history of vampires
Tell me a joke
[[speak:joke]]

¡OBLIVIATE

This is a joke:
{{joke}}

Tell me, is it funny:

[[boolean:funny]]
```

The key here is that when we are deciding if the joke is funny, we don't need the original context, so it's hidden. This speeds up generation and saved cost.



## More examples

- [Steps and Judgements for the Demo MI intervention](docs/mi/)

- [Step](syntax-exmaple.step)
- [Judgement](syntax-exmaple.judgement)
