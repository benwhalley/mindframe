---
title: MindFrame Architecture
---


### Overview

The goal of `mindframe` is to to build chatbots that leverage the power of LLMs to generate high-quality therapy, but remain introspectable and verifiable, even when implementing a complex intervention. We need to coordinate many models and orchestrate their ouptuts to create a coherent conversation with a client. This requires a database that tracks the state of the client as they move through sessions, and the intervention as a whole.


##### Why not just use Chatgpt or a fine tuned model?

We need the additional structure mindframe offers to:

- Reduce the 'load' on a single prompt/model to 'stay on track', even in a complex intervention with multiple components.
- Segment the implementation of different components of the intervention and so
- Allow better testing/validation of individual components
- Integrate relevant examples and case studies
- Build and integrate knowledge about the client into later prompting

There is quite a bit of 'plumbing' that needs to be written to
connect the different parts of the system and coordinate jobs etc.
Although we'll build it incrementally, this document describes what is needed
to enable intervention developers to create chatbots that are:

- theory led
- introspectable and monitorable
- safe and verifiable
- 'guidable', and so suitable for research and experimentation



### Costs, latency

For now, we want to build the best possible system. We don't care about cost or latency (although latency will become important in the medium term, and cost in the longer term).

Rationale:

A major goal is to generate a large corpus of high quality therapy to analyse. The easiest way to achieve this is to ignore latency for now and just build the best system we can. We can optimise latency later, and TPS rates are increasing quite rapidly, especially for smaller modules so even 'inefficient' designs might not be too slow in the future.

On cost: prices have already fallen by an order of magnitude in the last 18 months. That won't continue for ever, but we can expect prices to fall.
Moreover, the price of even the most expensive therapist means LLMs will always be cheap.

Back of envelope calculations:

- people speak at ~150 words per minute, so an hour of therapy = 9000 words per hour
- two tokens are roughly 1 word
- assume a 6:1 ratio of input tokens to output tokens for all llm prompts used
- lets assume we have to generate 10 hidden tokens for every token shown to clients
- tokens cost $2.50 per million tokens on input and $10 per million tokens on output

Some [chatgpt maths here](https://chatgpt.com/share/670e2135-1748-8001-a846-d1a470c0f5ef).

In short, it should cost < $2 per hour even with the most expensive current models.
Even if we're out by a factor of 10, it's still only $20 per hour which is peanuts for an on-demand therapist that scales to millions of users.

# Humans who will use `mindframe`

There are 5 distinct roles for humans:

- System developers/administrators
- Intervention developers who work to implement therapy manuals within the system
- Supervisors: human therapists or experts acting as supervisors to the system at runtime, or
- Trainers: human experts providing offline evaluations of performance
- Clients/patients

We avoid using the word "agent". Usage differs in CS and Psy, and it's ambiguous whether we mean the system/server/chatbot or the human/patient. Let's call the combined set of models and databases which produce output "the system".


# System 'primitives' and a common vocabulary

To build the system, we must define what 'primitives' are needed for encoding a therapy manual into a system that interacts with clients. Although LLM prompting will be a core mechanism for generating all output and processing all input, it's useful to have higher-level constructs to describe their organisation.

We should develop a common vocabulary for talking about these components. Some of the terms might get overloaded and have slightly different meanings i) colloquially, ii) in psychology, and iii) in computer science. So will need to be careful to define terms clearly.


As a possible starting point, these are the components of a treatment we need to define:


##### `steps`

`steps` are the components of an intervention. Key steps will be linked (by `transitions`) to form the main pathway of an intervention. However other steps may be 'islands':  individual, specific behaviours or tasks which a therapist may need to complete at any point during the intervention.

We leave open what each step is for, and their scope: This is determined by the treatment developer as they write the llm prompts and associated actions to operationalise their intervention. However in most cases steps are likely to be a single 'logical unit' of therapy which can be achieved within a single LLM prompt (e.g. 'establish rapport at the opening of a session', or 'identify discrepancies to build motivation').


##### `judgements`

`judgements` are a classification task. A judgement can be an evalution of the state of the system or the client, based on the conversation history or other data sources at a particular point in time. For example, we might want to evaluate whether the client is 'engaged in treatment', based on the conversation history and other data sources. A `judgement` is very similar to a `note`, but defines a structured classification task where the return values are known and can be defined by the treatment developer ahead of time. For example, we might want to evaluate whether the client is 'engaged' or 'disengaged' at a given point in time. This is a binary classification task, and the system would return a structured response (and perhaps also a textual explanation of the classification decision). Evaluations can be of both clients and therapists (or of the quality of the relationship).

Judgements can trigger further judgements or actions. This may always happen, or be conditional on specific classification responses. For example, if the system judges that the client is 'disengaged', it might trigger an alert action to warn a human supervisor, or a 'supervision' action which induces the therapist model to provide additional guidance or prompts which is included in step templates. `judgements` are created by writing an llm prompt. They may specify a particular model to use. Judgements are always logged, and the prompt or markdown file which specifies them includes the format for logging, what data to save etc. A `judgement` template uses pydantic to define the acceptable return values from the model. Multiple fields can be requested in the return value, allowing for multiple judgements to be made in a single prompt. For example, a prompt might ask the model to evaluate the client's engagement, adherence, and affective state. The model would return a JSON object with these fields, and the system would log them for later analysis.


##### `notes`

A `note` is a record made when a Judgement is enacted.

The `judgement` template specifies what return values are valid when the judgement is made, and these can either be structured/categorical values or unstructured textual notes. For example, a judgement might be used to summarise all of the turns within a step before transitioning to the next, or to combine information from multiple sources to record a snapshot of the client's affective state at a particular point in time. Other judgements would create `notes` that summarise or comment-on turn-by-turn utterances. For example, on each turn we might process client talk and therpist replies to label what is happening in the conversation.


##### `questions`

Another special case of judgements would be to record client responses to direct questions (these might be to measure their mood or other states).

In this case clients respond to questions defined in a step-like template and respond in freeform chat text. The question processing template would (like a `judgement`) validate/extract data from the response and store it. The schema for the return values (and so implicitly the judgement task) might be defined in the 'question step' as a convenience.

Alternatively, we might define questions using standard UI components like likert scales/radio buttons. In this case, the system would automatically validate the response and store it in the database.

Timeline: `#v2`



# Describing the desired thought processes and responses in text

`steps`, `judgements`, `notes`, `questions` and other primitives that compose an `intervention` are defined in markdown files. We also need to specify `transitions` and the conditions which apply when moving between steps.

The body of the markdown file is the text of the prompt to be sent to the LLM, and includes special extension tags which are used to access the conversation history, system state, or other data sources.

- Examples of llm prompts can be found in the `docs/fit/` directory, in files ending in `.step` or `.judgement`.

- See also how we will [access the prior conversation in prompts](#accessing-turns)


#### Multi-part or 'chain of thought' style prompts

By default, the system will support multipart prompting, inspired by LMQL or Microsoft Guidance, although simplified for this application.

Within a prompt, authors can specify 'output slots' which create interim completions that become part of the context for later completions. That is, a single prompt template can generate multiple calls to the LLM.

For example:

```
You are a therapist working with a client.
This is your recent conversation.

{{turns 30}}

Think about what is happening in this conversation.
Consider all the possible meanings in the context of CBT principles.

[[POSSIBLE_MEANINGS]]

Now, decide what to say to the client.
What is most important to address first?
What could be left to later?

[[PRIORITIES]]

Now, say something appropriate to the context.
Give your answer in spoken UK English.
Never ask more than a single question at a time.

[[RESPONSE]]
```





## Graphing the intervention

The intervention graph could be extracted from these files and shown in mermaid.

`for file in docs/fit/* ; do printf "===== %s =====\n" "$file"; cat "$file"; done`

Then copy to chatGPT with the instruction to:

EXTRACT THE GRAPH FROM THIS TEXT AND SHOW IT IN MERMAID IN A FORMAT LIKE THIS:

```
graph TD;
  A[elicit-discrepancy.step] -->|"discrepancy==yes"| B[embed-motivation.step];
  A -->|"disrepancy==partial + step.turns > 30"| B;
  B -->|step.minutes > 5 + step.turns > 5| C[end-intervention.step];
```



# Implementation notes

## Validation rules for markdown/yaml files describing interventions

- all files in an intervention have a unique `title`

- all note templates includes at least one `[[NOTE]]` tag which is the completion that is saved as the note. If multiple `[[NOTE]]` tags are includes, multiple notes are saved in the database.

- all `judgements` define a `return`  value in the yaml frontmatter (this is done in a serialised form of a pydantic model, which specifies the schema for the return value).

- as a preflight check, it might be worth parsing and trying to render all templates with an empty context? This would catch any syntax errors in the templates, and also any missing/broken tags or other issues.



# Starting an intervention episode

A client starts using the system, and this creates an `episode` of therapy and a `session`.

An intervention always has a 'root' step, where all clients start.

Subsequent sessions can either start on the last step of the previous session, or at the root step, or at some other step. This is defined in `config.yaml`.


# While on a step...

The client is always 'on' a step.

The system tries to move to the 'next' step, defined in the transitions section of the yaml header.

To do this, it needs to evaluate the list of `conditions` in the yaml.
The list is evaluated in order, and if any of them eval true then the transition occurs

Conditions can be simple python expressions and have access to some variables (like the return values of judgements, and the current step and turn number)


# Where to go next?

Most of the time, a step will define a transition to the next step in the intervention along with conditions to meet.

However there are some cases where the next step needs to be inferred.  For example, a "digression" is a step which users can jump to at any point, and  has no specific onward path.

A "recap" step (at the start of a new session) would be an example of this.

In this instance, the system uses the history of which steps have been visited to infer the next step.

i.e. if a client completes a step with no specific transition step specified they will be returned to the 'last visited step'.




# Recording turns

Each time the client says something or the system responds, we need to record a Turn

```python
class Turn(models.Model):
    timestamp = models.DateTimeField()
    episode = models.ForeignKey(Episode)
    text = models.TextField()
    speaker = models.CharField(choices=['client', 'therapist', 'system'])
```

# Making `judgements`



# Making `notes`

Making notes involves:

- using an llm prompt template
- populating it with context
- making completion(s) named by the `[[NAME]]` syntax in templates
- saving each completion as `note`s in the database with a timestamp

This can happen in parallel with other actions.




# Defining and using `example`s

Examples are used to provide additional context to the therapist model, and to provide examples of good practice for the therapist model to follow. We create them in markdown for convenience, but they are stored in the database and used for semantic search and RAG.

The basic form is:

- tags
- commentary: explanation of why the speech good or bad practice example
- is_positive_example: boolean, default true
- text: the text of the example, normally in a `CLIENT: ... ; THERAPIST, ...` format

The database stores embeddings for commentary, text, and all combined (including tags).

We can lookup good or bad examples from within templates using the tag syntax defined below.




```python
class Note(object):
    template = models.TextField()

    timestamp = models.DateTimeField() # time when template is populated with context
    episode = models.ForeignKey(Episode)

    prompt = models.TextField() # text of prompt with tags called and context filled in
    text = models.JSONField() # dict, keys defined by names of `[[NOTE]]` tags in template, vals=completion text
    meta = models.JSONField() # any additional metadata about the note like llm model used, API return data etc
```
















## Logging and extraction of data

Here is a list of the core **primitives** in the `mindframe` system, which structure the architecture of interventions:

- **Steps**: Core units of the intervention, which can be linked via transitions. Each step typically aligns with a logical unit of therapy or LLM prompt.

- **Turns**: Sequential exchanges between the system and the client, with each turn logged for later use or evaluation.

- **Transitions**: Define pathways between steps and the conditions required for advancing from one step to another. **Digressions**: are temporary transitions to steps outside the primary intervention flow, with an intention to return to the main pathway.

- **Judgements**: Structured classification tasks where the system evaluates conversation state and returns defined responses. These are used to determine transitions or influence step behavior.

- **Notes**: Free-text summaries or reflections, similar to judgements but unstructured. They provide insights into conversation progress for review or system reflection.

- **Questions**: Direct prompts for the client, where responses are logged, processed, and stored. They can be designed to elicit structured or free-form inputs, similar to judgements.

- **Actions**: Side effects or additional steps triggered when certain transitions or conditions are met (e.g., triggering a note or alert).

- **Examples**: Snippets of good or bad therapeutic practice stored for semantic search or RAG retrieval during the conversation.

- **Theory**: Other background materials or standardized information made available in the intervention templates to maintain consistency across different templates.


What follows is a short description of how these components might link together:


##### Steps and the logical units of therapy

**`steps`** are the basic components of an intervention. Key steps will be linked by `transitions` to form the core pathway of the intervention. Other steps may be 'islands' --- individual, specific behaviours or tasks which a therapist may complete at any point during the intervention.   We leave open what each step is _for_, and their scope: This is determined by the treatment developer as they write the prompts and associated actions and define their intervention. A step could be simple a a single LLM prompt like "You are an MI therapist, establish rapport with the patient. Start by asking them about their day".

In most cases steps are likely to be a 'logical unit' of therapy which can be achieved in a single LLM prompt (e.g. 'establish rapport at the opening of a session', or 'identify discrepancies to build motivation').  Simpler, 'island' steps might be used to create a `digression`, e.g. to 'give health information' or 'take an affect measurement' from the client (more on this below).

*Techniques* within a psychological intervention might be implemented within either single `step`, plus associated `judgement`, or by linking together multiple steps. For example, eliciting imagery in MI might be a single step with the goal to meet the judgement 'has patient generated an image of their problem?'. Or it might be a sequence of steps with multiple judgements, like: 'has patient generated an initial image of their problem', followed by an invitation to 'make it more concrete' and the judgement/goal 'has the patient described additional details for the image?'.

Steps are implemented as templated llm prompts which are evaluated _in the context of the current conversation_. Although the same step may be repeated multiple times, the response of the agent will change because the conversation context builds. Each time the client responds or a step is repeated, a `turn` occurs.


##### Taking turns in conversation

We envisage treatment as a chatbot (or spoken-word chatbot), that is inherently sequential.
The system and client take turns to speak, and each turn is logged.

Logging of `turns` is important because it provides context for later step evaluation. All client inputs are recorded as a separate turn. Evaluating a `step` may create multiple texts or other metadata to log — for example, a prompt might specify multiple generations from the model, for a `[THOUGHT]`  and an `[REPLY]` which are both logged and available for later use in templated prompts.


##### Progress through an intervention

**`transitions`** define the paths allowed between steps, and the conditions required for transitions to occur. They are defined alongside `steps` (as part of the same file).

In some cases we might explicitly define a transition to an 'unknown' target node. In this case we create conditions for completing the current step, but provide no explicit target. This would be used for 'digressions' or 'measurements' which are not part of the main flow of the conversation - i.e. the 'happy path'.

The conditions for a transition are defined by the treatment develop using simple expressions (see the step template examples) in the yaml front matter. In defining conditions, developers can refer to  `judgements` which the system makes of the current state of the conversation (i.e. all saved ata) at a particular point in time.

For example, before moving to the next step we might want to evaluate *whether the client is engaged in treatment*.

A `judgement` is very similar to a `note` (see below), but defines a structured classification task where the return values are known and can be set by the treatment developer ahead of time.  If we want to judge whether the client is 'engaged' or 'disengaged' at a given point in time this is a binary classification task, and the system would return a structured response. Because we are (presently) using llms for classification (or may do) the model could also return a textual explanation of the classification decision for introspection purposes.

Both `notes` and `judgements` are created by writing an llm prompt. These may specify a particular llm model to use (e.g. cheap/expensive).
In future, if we use non-llm classifiers for judgement then their template would still need to define how system data and data from the conversation is presented to the model, and the schema for the return value.

Although not required, 'judgements' return values might be the trigger for further judgements or actions. This may always happen, or be conditional on specific classification responses. For example, if the system judges that the client is 'disengaged', it might trigger an alert action to warn a human supervisor, or a 'supervision' action which induces the therapist model to provide additional guidance or prompts which is included in subseuqent step templates.

A `judgement` template uses objects inheriting from Pydantic BaseModel to define acceptable return values from the model. This means even when using llms we can use `magentic` to guarantee structured data is returned from the model, and we can rely on the schema of the return values. Multiple fields can be requested in the return value, allowing for multiple judgements to be made in a single prompt execution. For example, a prompt might ask the model to evaluate the client's 'engagement', 'adherence', and 'affective-state'. The model would return a JSON object with these in separate fields, and the system would log them for later use/analysis.

We can attach **`actions`** to transitions which create side effects for the transition. For example, we might want to trigger a clinical note to be made every time the client moves to a new step. This would be an action which is triggered by the transition.


##### Keeping good notes and reflecting on progress

In defining the intervention, the treatment developer can explicitly define ways in which the system should reflect and summarise on progress to inform it's practice. Notes can be very short and serve as a practical tool to compress the information provided to later steps (e.g. summarising the conversation in step A to inform step B). They could also be more detailed and serve as a record of the conversation for later review by a human supervisor, or for research purposes (e.g. to aid introspection about system behaviour and futher intervention development).

A **`note`** is a special case of a judgement and uses the same machinery, but is syntactic sugar for a judgement where the only return values are *unstructured* text.

For example, a note template might generate completions which are summaries of the recent conversation history (see examples). This `note` template would specify _how_ to summarise conversations within a step before transitioning, or combine information from multiple sources to record a snapshot of the client's affective state.

Another special use of `notes` would be to summarise or comment on turn-by-turn utterances. E.g. on each turn we might process client talk and therpist replies to label what is happening in the conversation in real time (e.g. to help human supervisors).



##### Eliciting structured inputs from the client

`questions` are another special case of judgements used to record client responses to direct/specific questions. For example: to measure clients mood or other states. In this case clients respond to questions defined in a `step`-like template, and respond in freeform chat text.

The question-processing-template would validate/extract data from the response and store it (same as for a `judgement`).

The schema for the return values might be defined in the 'question step' as a convenience. That is, `*.question` files would combine elements of  `.step` and `.judgement` files.

Alternatively, we might define questions using standard UI components like likert scales/radio buttons. In this case, the system would automatically validate the response and store it in the database. See examples in the `fit/` directory for how this might be implemented.



##### Responding to client context but: digressions

Sometimes we want to allow the system to `digress`: A digression means to temporarily move the client to a different step, outside the primary/happy flow of the intervention, but *with the intention of returning to the current step*.

For example, if the client asks a question which is off-topic but important to address, then system might `digress` to a 'information-giving' step and answer that question, but then return to the previous step. Similarly, we might want to 'measure' something about the client: we could achieve this by 'digressing' to a question step and then return to the current step. This could be implemented by keeping track of the chain of steps visited then when digression steps are completed without a specified target the system returns to the last visited step.





# Describing the intervention in markdown/jinja2

`steps`, `judgements`, `notes`, `questions` and other primitives that compose an `intervention` are defined in template files.

Template files all use:

- yaml header sections to specify metadata about the step.
- markdown body sections, with jinja2 tags to control the templated output

This format is similar to existing Rmarkdown and Quarto files, so fairly familiar to researchers and will be easy to collaborate on/version/track changes.

Tools exist to parse and validate them too, so we can use these to ensure the files are well-formed and consistent.

Metadata in `step` files will include transitions and conditions for transition, specify llm models to use for the prompt, or define actions or notes to take. Metadata in `judgement` files will define possible return values and any actions to trigger.


### Template bodies become LLM prompts

The body of the markdown files is the text of the prompt to be sent to the LLM (once variable substitutions have been made).

This can include special extension tags which are used to access the conversation history, system state, or other data sources. We can use jinja2 syntax to specify control structure like loops, property access, or extension tags.

We will provide some common 'context' to all step and judgement templates, to enable variable substitutions when they are rendered:


##### 'Theory' and 'intervention background'

An intervention can define `.theory` files and make their body available as a dict of strings. This enables all templates to access standardised background information about the intervention and keep things DRY.

E.g., the `core_concepts.theory` file could be loaded and exposed as a template variable:

`{{intervention.core_concepts}}`

Similarly, the `intervention` key from the `config.yaml` file would be exposed in templates as:

`{{intervention.title}}` (== "Functional Imagery Training")


And finally, files which end with  `.persona` or the `personas` key from the `config.yaml` are loaded and is exposed as:

`{{personas.therapist}}`


##### System state

Other system information is exposed in templates too:

`{{step.turn}}` = returns an integer >= 1

`{{step}}` exposes the current step, so `{{step.title}}` could be used in a judgement template



# Description of runtime behaviour/operations

This is intended as a rough sketch/definition of requirements for how the system would operate at runtime.


## Starting an intervention episode for a new client

A client logs on and gains access to the system in some way, web based initially.

This will need to be authenticated.
Initially we should just use email + magic links.

[We can develop this later, but a lot of it would be needed for pilot studies anyway so worth considering early]


---

The client starts interacting with the chatbot, and this creates an `episode` of therapy and a `session`. These are objects which are persisted in the db.

An intervention always has a 'root' step, where all clients start, so the current_step of the session is set to this.

If the client ends the session (explicitly or by timeout) then the session is closed.

When they return, a new session is created. Subsequent sessions can either start on the last step of the previous session, or at the root step, or at some other step (this is defined in `config.yaml`).


## While the user is 'within' a step

The client is always 'on' a step. This is saved as the `current_step` of the session.

Step history is preserved as a linked list of steps visited.

The system is always trying to move to the 'next' step, defined in the `transitions` section of the yaml header of the current step.

To do this, the system needs to evaluate the list of `conditions` in the yaml.
The list is evaluated in order, and if any of them eval true then the transition occurs.

If no conditions eval true, then the system remains on the current step, and the step template is populated and re-rendered for the client.

Step templates always include a completion called `[REPLY]` which is the text that is sent back to the user.



##### Evaluating conditions for transitions

Conditions in the yaml of a step can be simple python expressions and have access to similar variables as the template itself, as well as the return values of judgements.

A simple condition might be `step.turn > 5` to check if the client has been on the step for more than 5 turns.

A judgement-based condition might state `judgement.slug == 'disengaged'` to check if the judgement with filename `slug.judgement` has returned the value 'disengaged'.

If judgements return numeric values then we could also say things like: `judgement.slug > 3`



## Deciding which step is next

Most of the time, a step will define a transition to the next step in the intervention along with conditions to meet. However there are some cases where the next step needs to be inferred or specified by config values.

For example, a "digression" is a special `step` which users can jump into at any point, but which has no specific onward path, i.e. has no specific transitions defined to other steps.

A "recap" or "revision" step, used to start a new session, might be an example of this.

A revision step might reference previous conversation history and engage in conversation to remind the client of what they discussed, or specific topics from the conversation. After some condition is met (perhaps 5 turns have passed?) then revision is complete and the system wants to move the the 'next' step.

Because the revision step doesn't provide a specific transition to a 'next' step, the system needs to infer what the next step should be.

In this instance, the system would use the history of which steps have been visited to infer the next step.  i.e. if a client completes a step with no specific transition step specified they will be returned to the 'last visited step'.



## Recording turns

Each time the client says something in the chat or the system responds, we need to make a record of the turn including at least this information:

- `timestamp`
- `episode` this conversation is within
- `step` the current step
- `values` : a dict of all the completions made when executing the turn (if it was a therapist turn), e.g. `[THOUGHT]`  and `[REPLY]`
- `text` - a shorthand for the `[REPLY]` completion (or the client's input)
- `speaker` (client, therapist, system)
- `meta` (any additional data like the time taken to respond, the content of the response, etc)


## Accessing turns in templates {#accessing-turns}

Turns can later be accessed in templates using the follwing django/jinja syntax, or by extension tags:

`{{turns }}` -- this would (by default) include all the turns in the current session.

`{% turns 3 %}` -- this shows last 3 turns in the session - i.e. equivalent to `session.turns()[-3:]`


The output format for turns would default to:

```
{% for t in turns %}
{{t.speaker|uppercase}}: {{t.text}}
{% endfor %}
```

So the output of `{% turns 3 %}` would look like:

```
CLIENT: I'm not sleeping well at the moment
THERAPIST: I'm sorry to hear that. What's been happening?
CLIENT: I'm just really stressed out
```

`step`, `session` and `cycle` objects will be available in the context, and each of these object types has a `turns()` method, so could be used with the turns tag to constrain which turns are included:

`{% turns step %}`  -- shows all turns from current step, where `step` is the current step object

`{% turns session %}`  -- shows all turns from current session

`{% turns cycle %}` -- shows all turns from current cycle

`{% turns step.previous %}` - turns from previous step (`previous` is an attribute on step).



#### Using RAG on turns

We could also use RAG to search for previous turns which match a particular pattern, e.g. to find all turns where the client expresses a negative emotion, or where discussion was about alcohol use, to ensure it's possible to do callbacks and reflections effectively.

`{% turns cycle -1 filter="alcohol_use" method="similarity" %}`

In future the lookups could use other variables available to templates, e.g. the `primary_problem`

`{% turns 'step' -1 filter=meta.primary_problem method="hyde" %}`

In this example, we would use hyde to generate "client/therapist talk abotu {filter}" and then do semantic search based on that.

We would have to experiment, but I thnk it's likely that we'd need to provide tools to control the 'window' around matching turns, and to organise the output of turns. For example imagine this dialog:

```
1 CLIENT: I'd like to drink less
2 THERAPIST: Why do you want to drink less?
3 CLIENT: I'm worried about my health
...
8 THERAPIST: What are you worried about?
9 CLIENT: Liver damage
```


If we search for similarity to "alcohol misuse and consequences" we might match lines 1, 2, and 9. But we might want to return the whole dialog, or at least return lines 3 with line 2 and line 8 with line 9.

If we set a default window = 1 then we would include all of these lines in the output.
However, we'd also need to decide what order to return them in. The similarity scores alone wouldn't be a good guide, because line 9 might be more similar than line 8, but it would be better to return in conversational order to show the conversation. TODO: specify the searching and sorting algorithm for presentation.

We should set a default for presenting turns in the template, but allow the user to override this with a `format` parameter (see `turns-default.jinja2` and the `format` parameter in the `examples` tag below).


##### Excluding smalltalk

To save tokens, we might want a parameter to exclude smalltalk and chit chat from previous turns. This could be done by filtering out turns which are too short, or which don't contain certain keywords, or we use a special classifier on ingress.

`{% turns 'step' smalltalk=false %}`



##### Including/excluding therapist "thoughts"

As part of their execution, step prompts might generate multiple completions. For example, a step might generate a `[THOUGHT]` and a `[REPLY]` completion.

We could include these in the turn history too, but sometimes we might want to exclude them.

`{% turns 'step' thoughts=false %}`

Display of thoughts is shown in the default template (and implementing this feature would mean creating an alternative template).




## Making `notes` using note templates

Note templates are defined in `*.note` files.

Making notes involves:

- using an llm prompt template (the body of the .note file)
- populating it with context, or calling jinja tags
- making llm completion(s) named by the `[[NAME]]` syntax in templates (this happens iteratively because some completions require earlier completions as context)
- saving each completion as a `note` in the database with a timestamp

Making notes can happen in parallel with other actions so could be queued.

A note would have at least these fields:

- `template`: which note template (or judgement) was used
- `timestamp`: when the note was made
- `episode`: the episode this note is part of
- `key`: a unique identifier for the note, defined by the `[[NAME]]` tag in the template
- `text`: the text of the note



## Making `judgements`

In practive, at runtime, judgements are a lot like making a `note`, except:

- judgements can't happen in parallel (?) because step transitions depend on them
- the return value is structured and defined by the treatment developer ahead of time

After making a judgement, the system records a special type of note which also includes the structured classification result. This could maybe be stored as a JSON field which serialises the pydantic response model instance?



## Accessing notes and judgements within templates

After a note or judgement has been made, we can lookup the result of judgements in other templates using a special template tag.

E.g.: `{{judgement.slug_of_judgement.last}}`

`{{judgement.slug}}` is shorthand for `{{judgement.slug.last}}` and by default returns the value

`{{judgement.slug.last.timestamp}}` also possible (or access other fields saved with the judgement).

`{{judgement.slug.all}}` would return a list of all the judgements made with that slug in the current episode, so you could write:

{% for j in judgement.slug.all %}
- {{j.timestamp}}: {{j.value}}
{% endfor %}


Similarly for notes, we could write:

`{{note.slug.NAME}}` to access the text of a note with a given name. If multiple records exist, return the last.

`{{note.slug.all}}` to access all notes with a given slug in the current episode (this returns a list of dicts which NAMEs as keys)


Alternative tag-based syntax for notes:


`{% notes "*" %}` include all notes

`{% notes 10 %}` include last 10 notes

`{% notes 'formulation' %}` include all notes generated by the `formulation.note` template.




## Defining and using `example`s

Examples are used to provide additional context to the therapist model, and to provide examples of good practice for the therapist model to follow.

We create them in markdown files with `*.example` extensions for convenience, but they are stored in a database and used for semantic search and RAG.

We might use postgres/PG_VECTOR for RAG because we can combine it with other data sources easily.

The basic form for ingestion/storage is:

- `tags`
- `commentary`: explanation of why the speech good or bad practice example
- `is_positive_example`: boolean, default true
- `text`: the text of the example, normally in a `CLIENT: ... ; THERAPIST, ...` format

- embedding of the `text`
- also, separate embeddings for commentary, text, and all combined (including tags)??


We can lookup good or bad examples from within templates using a jinja tag syntax similar to that of notes.

E.g., this uses semantic search (default method) to find best 5 matching examples

```jinja
{% examples
    "How does your problem affect you in daily life?"
    max=5
%}
```

In future we might implement other search methods, e.g. [hyde](https://docs.haystack.deepset.ai/docs/hypothetical-document-embeddings-hyde). Here the search string states what we want rather than being an example of what we want, because hyde allows this?

```jinja
{% examples
    "therapist asking about problems in daily life"
    method='hyde'
    max=5
%}
```


We could also do simple tag lookups.

Include first 10 examples with 'imagery' tag:

`{% examples tags='imagery' max=10 %}`

More dynamic/contextual lookups for examples could be done if we use `turns` to do the search.

This tag would include the past 3 turns as the search string, and return 5 examples of good practice which are most similar to those utterances:

`{% examples method='turns:3' max=5 %}`

Parameters for the `examples` tag we might implement:

- search string (allways the first, optional, positional param)
- `max` number of examples to return
- `method`: 'semantic' (cosine similarity) or 'hyde' or 'turns:N' (default N = 2)
- `tags` to restrict search to
- `template`: the format/template to output the examples in (default shown below) - accepts the name of a jinja template. See examples-default.jinja2 for the default template.





# Graphing the intervention

The intervention graph could be extracted from these yaml/markdown files.

I'm not sure if the system itself needs to explcitly represent the graph, but it might be useful when authoring to be able to show it in mermaid.

This is a quick and dirty way to see a graph:

`for file in docs/fit/* ; do printf "===== %s =====\n" "$file"; cat "$file"; done`

Then copy to chatGPT with the instruction to:

EXTRACT THE GRAPH FROM THIS TEXT AND SHOW IT IN MERMAID IN A FORMAT LIKE THIS:

```
graph TD;
  A[elicit-discrepancy.step] -->|"discrepancy==yes"| B[embed-motivation.step];
  A -->|"disrepancy==partial + step.turns > 30"| B;
  B -->|step.minutes > 5 + step.turns > 5| C[end-intervention.step];
```
