---
title: Architectural notes for MindFrame (FIT-chatbot system).
---


### Preface

Our goal is to build a chatbot which leverages LLMs, but
doesn't depend on a specific model for all interactions. 

We want to be able to coordinate multiple models, and integrate them with a database that tracks the state of the client as they move through sessions, and the intervention as a whole.

We need this structure to do things like

- reduce the load on a single prompt/model
- separate out individual components of the intervention and allow better testing/validation of individual components
- integrate relevant examples and case studies
- build and integrate knowledge about the client into later prompting


There is quite a bit of 'plumbing' that needs to be written to 
connect the different parts of the system and coordinate jobs etc.

Although we'll build it incrementally, I think it's what we would need 
to enable intervention developers to create chatbots that are:

- theory led 
- introspectable/monitorable, rather than just a black box
- safe (and verifiable)
- 'guidable', so suitable for research and experimentation


# Costs and speed

For now, we want to build the best possible system. We don't care about cost or latency (although latency will become important in the medium term, and cost in the longer term).

Rationale: 

A major goal is to generate a large corpus of high quality therapy to analyse. The easiest way to achieve this is to ignore latency for now and just build the best system we can. We can optimise latency later, and TPS rates are increasing quite rapidly, especially for smaller modules so even 'inefficient' designs might not be too slow in the future.

On cost: prices have already fallen by an order of magnitude in the last 18 months. That won't continue for ever, but we can expect prices to fall. 
Moreover, the price of even the most expensive therapist means LLMs will always be cheap.

Back of envelope: 
- people speak at ~150 words per minute, so an hour of therapy = 9000 words per hour
- two tokens are roughly 1 word
- assume a 6:1 ratio of input tokens to output tokens for all llm prompts used
- lets assume we have to generate 10 hidden tokens for every token shown to clients
- tokens cost $2.50 per million tokens on input and $10 per million tokens on output


Some chatgpt maths here: https://chatgpt.com/share/670e2135-1748-8001-a846-d1a470c0f5ef

It's going to cost < $2 per hour even with the most expensive current models.

Even if we're out by a factor of 10, it's still only $20 per hour which is peanuts for an on-demand therapist which scales to millions of users.



# Roles/names of different humans involved in using `mindframe`

I envisage 4 primary roles for humans:

- system developer (i.e. Ali!)
- intervention developer (i.e. Jackie or others who want to convert therapy manuals to chatbots)
- clients (i.e. patients)
- supervisors: human therapists or experts acting as supervisors to the system at runtime, or providing offline evaluations of performance

I think we should avoid using the word "agent" because it's ambiguous whether we mean the system/server/chatbot or the human patient because usage differs in CS and Psy.

Let's call the combined set of models and databases which produce output "the system" or the "chatbot".

These user types each have different needs for UI to be met (see below).




# System 'primitives'

In building the system, we need to think about what 'primitives' are needed for encoding a therapy manual into a system that interacts with clients.

We should develop a common vocabulary for talking about these components. Some of the terms might get overloaded and have slightly different meanings i) colloquially, ii) in psychology, and iii) in computer science, so will need to be careful to define terms clearly.

As a possible starting point, these are the components of a treatment we need to define:

- `steps` are th basic components of an intervention. Key steps will be linked by `transitions` to form the core pathway of the intervention. Other steps may be 'islands' --- individual, specific behaviours or tasks which a therapist may complete at any point during the intervention.  We leave open what each step is _for_, and their scope: This is determined by the treatment developer as they write the prompts and associated actions and define their intervention. However in most cases steps are likely to be a single 'logical unit' of therapy which can be achieved in a single LLM prompt (e.g. 'establish rapport at the opening of a session', or 'identify discrepancies to build motivation'). Simpler, 'island' steps might 'give health information' or 'take an affect measurement' from the client. Steps are implemented as templated llm prompts which are evaluated _in the context of the current conversation_. This means that, although the same step may be repeated multiple times, the response of the agent will change because the conversation context builds. Each time the client responds or a step is repeated, a `turn` occurs. 
Logging of `turns` is important because it provides context for later step evaluation. All client inputs are recorded as a separate turn. Evaluating a `step` may create multiple texts or other metadata to log — for example, a prompt might specify multiple generations from the model, for a `[THOUGHT]`  and an `[OUTPUT]` which are both logged and available for later use in templated prompts.

- `transitions` define the paths allowed between steps, and the conditions required for transitions to occur. In some cases we might explicitly define a transition to an 'unknown' target node. In this case we have conditions for moving to the next step, but no explicit target. This would be used for 'digressions' or 'measurements' which are not part of the main flow of the conversation. We can also attach `actions` to transitions which create side effects for the transition: for example, storing information in the database or triggering a 'supervision'.

`actions` the system can take are defined by functions which take the current context as input. Actions can also be chained (so the result of one action might be to trigger additional actions). Standard actions will be provided for:

- `judgements`: i.e., a judgement about or evalution of the state of the system or the client, based on the conversation history or other data sources at a particular point in time. For example, we might want to evaluate whether the client is engaged in treatment at a given point in time, based on the conversation history and other data sources. A judgement is very similar to a note, but creates a structured classification task where the return values are known and can be defined by the treatment developer ahead of time. For example, we might want to evaluate whether the client is 'engaged' or 'disengaged' at a given point in time. This is a binary classification task, and the system would return a structured response (and perhaps also a textual explanation of the classification decision). Evaluations can be of both clients and therapists (or of the quality of the relationship). 

Judgements can trigger further judgements or actions. This may always happen, or be conditional on specific classification responses. For example, if the system judges that the client is 'disengaged', it might trigger an alert action to warn a human supervisor, or a 'supervision' action which induces the therapist model to provide additional guidance or prompts which is included in step templates. `judgements` are created by writing an llm prompt. They may specify a particular model to use. Judgements are always logged, and the prompt or markdown file which specifies them includes the format for logging, what data to save etc. A `judgement` template uses pydantic to define the acceptable return values from the model. Multiple fields can be requested in the return value, allowing for multiple judgements to be made in a single prompt. For example, a prompt might ask the model to evaluate the client's engagement, adherence, and affective state. The model would return a JSON object with these fields, and the system would log them for later analysis.

- `note`: A note is a special case of a judgement and uses the same machinery, but is syntactic sugar for a judgement where the only return values requried are unstructured text. For example, the template might generate summaries of the recent conversation history. The `note` template would specify how to summarise conversations within a step before transitioning, or combine information from multiple sources to record a snapshot of the client's affective state.  Another special use of `notes` would be to summarise or comment on turn-by-turn utterances. E.g. on each turn we might process client talk and therpist replies to label what is happening in the conversation. 

- `questions` Another special case of judgements would be to record client responses to direct questions to measure their mood or other states. In this case clients respond to questions defined in a step-like template and respon in freeform chat text. The question processing template would (like a judgement) validate/extract data from the response and store it. The schema for the return values might be defined in the 'question step' as a convenience. Alternatively, we might define questions using standard UI components like likert scales/radio buttons. In this case, the system would automatically validate the response and store it in the database.


# Describing the therapy in markdown

`steps`, `judgements`, `notes`, `questions` and other primitives that compose an `intervention` are defined in markdown files. These files use yaml header sections to specify metadata about the step. Metadata might include conditions for transitions, actions to take, or specify llm models to use for the prompt. 

Transitions between steps are defined in the yaml frontmatter.

The body of the markdown file is the text of the prompt to be sent to the LLM, and includes special extension tags which are used to access the conversation history, system state, or other data sources.


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





Types of 'memories' we can make:

- turns (what each person said, and prior/hidden reasoning attached to the therapist's utterances)
- evaluation (a structured judgement about the state of the system or the client)
- notes (an unstructured record or summary of the state of the system or the client)

Notes types can be namespaced to help general access and inclusion in templates later e.g. 

- `turn.text`
- `evaluation.affective`, `evaluation.adherence`, `evaluation.other`
- `meta.user`, `meta.system`, `meta.other`
- `system.log` or `system.log.llm_call`

Each memory would store these fields:

- `key` (a unique identifier for the memory)
- `timestamp`
- `category` (a dotted-string type identifier for the memory, e.g. 'turn', 'evaluation', 'note')
- `name` (a human-readable slug-type identifier for the memory, not necessarily unique)
- `text` (the text content of the memory)
- `audio` (any audio content of the memory)
- `meta` (explanation or additional context to help interpret the memory. e.g. the chain of LLM prompts used to generate the memory with COT)





- `digress`: this means to temporarily move the client to a different step, outside the primary flow of the intervention, but with the intention of returning to the current step. For example, if the client asks a question which is off-topic, the system might digress to a 'information-giving' step and answer that question, and then return to the previous step. Similarly, we might want to 'measure' something about the client: we could achieve this by 'digressing' to a measurement step and then returning to the current step. This could be implemented by marking the current step as an 'exit' and then when digression steps are completed without a specified target the system returns to the 'last exit'.

- `supervise`: i.e., provide additional guidance to the therapist model

- `alert`: i.e., trigger an alert to the system developer or human supervisor. This could be used to flag up dangerous or unexpected responses from the client or therapist model. For example, if the client is asking for medical advice, the system might trigger an alert to the system developer or supervisor to intervene (i.e. if a 'digression' to a special-case step, to explain that the system can't offer medical advice, is insufficient).



In addition, 



intro.build_rapport
intro.elicit_problem
intro.elicit_goals
motivate.identify_pros_cons
motivate.elicit_change_talk
motivate.elicit_importance
practice.elicit_imagery
practice.elicit_change_plan
practice.set_homework














Step
Transition
Evaluation


Turn



And these are 'state' which might be saved at runtime by the system, or developed over time.

- `turns`
- `indicators`
- `measurements`
- `examples`
- `supervision`
- `notes`
- `preferences`
- `evaluations`

Intervention developers will need to write some or all of these primitives in a declarative language which the system can interpret and use to generate prompts for the therapist model.








### `steps`

`steps` are nodes in the DAG which represent a particular state in the therapy, and are likely to be achievable using a single LLM prompt. They may not be achievable in a single 'turn' of the conversation, but they are a single 'unit' of the intervention. A step is mostly concerned with defining the content of the conversation at a given point within the session, and not the broader structure of the conversation. A step could be simple a a single LLM prompt like "You are an MI therapist, establish rapport with the patient. Start by asking them about their day".

'Techniques' within a psychological intervention might be implement within either single `step`, plus associated `goal`, or by linking together multiple steps. For example, eliciting imagery in MI might be a single step with the 'goal' of 'has patient generated an image of their problem'. Or it might be a sequence of steps with multiple goals, like 'has patient generated an initial image of their problem', followed by an invitation to make it more concrete and the goal 'has the patient described additional details for the image'.


### `turns`

`turns` are individual utterances by the patient or the system. A turn may be a response to a prompt, or a prompt itself. Turns are not part of the treatment definiton, but are the 'atoms' of the conversation. We'd want to store each turn in the database for later analysis and possible use in RAG, along with metadata like the time taken to respond, the content of the response, etc.

### `goals`

`goals` are a description of something which must be achieved in the therapy, ie. within the steps of the intervention. Goals might require multiple steps to achieve, but could also be smaller and achieved within a single step. As examples, a goal might be to 'establish rapport' or 'identify a problem to work on in treatment'. The system needs to be able encode goals as partially or fully completed (and possibly as failed). To begin with we might simplify and encode goal states as binary (achieved/not achieved). Goals are evaluated with respect to various data sources including the current state and history of the conversation using one or more other `goals` or `indicators` (see below).


### `transitions`

`transitions` are the edges in the therapy DAG, which represent the possible transitions between `steps`. 

Transitions are associated with a set of conditions which must be met for the transition to be valid/occur. These conditions are defined by `goals` which have been achieved, and potentially also other data (e.g. the time or the number of turns taken in the step, or client metadata).  When transitions are evaluated, they may have side effects and pass information back to the next `turn`, or implement other logic in `actions`. 

For example, consider a transition between nodes for 'establish_rapport' and 'elicit_problem'. The transition might require that the patient meets the goal 'is_engaged'. If the patient is not engaged, the transition might fail, and the system could either simply allow more turns to happen within the 'establish_rapport' step, or inject additional system information into the chat history/prompt (not seen by the client), e.g. to say "Client does not seem engaged yet, keep trying." or "Client does not seem engaged yet, try strategy X.". That is, providing additional online `supervision` to the therapist to supplement the initial prompt and help them get across the transition boundary.


### `indicators`

`indicators` are related to goals, but are a representation of some state of the client or the conversation/dyad at a particular time, evaluated on the basis of data available to the system (but not specific questions asked of the client... those are `measurements`, see below)

We can think of them as a single continuous measurement, rather than an *evaluation* of state of the whole system at a single point in time (which goals are). 

`indicators` and `measurements` both feed into goal evaluation. For example, we might have a continuous indicator of 'client engagement' or of 'negative arousal' which are updated at each step of the conversation and stored as metadata with 'turns' (see below). Indicators could be defined in various ways and use different data sources, but could be entirely text based (e.g. from last N turns). We should be able to define indicators in a declarative way, and then have the system automatically update them based on the conversation and other inputs. 

Indicators might have various return 'types'. For example binary indicators (e.g. 'client is engaged') or continuous indicators (e.g. 'emotional arousal'), or categorical indicators (e.g. 'dominant emotion').  Initially, I'd expect indicators to be implemented in a fairly brute-force way as templated prompts to the LLM (like `steps`). This has the advantage that we can use explcit prompting to define them and update them easily in development. But later we might want to be more subtle and train specific models to do these categorisation tasks (e.g. to save time/cost).


Indicators might use custom code, or a similar templating syntax to steps if being implemented with llms (more on this below). But, for example, one indicator might be:


```{#indicator:empathy}
You are a therapy supervisor for FIT therapists
We want to check they are doing a good job.

These are the most recent turns in the conversation:

{turns:5}

Is the therapist providing suitable empathy to the client?
Think about it step by step:

[[DISCUSSION]]

Now, respond yes or no.

[[RESPONSE]]
```


Or:


```{#indicator:engagement}

You are a therapy supervisor for FIT therapists
We want to check they are doing a good job.

These are the most recent turns in the conversation:

{turns:12}

Is the client engaged in the conversation?

Think about it step by step:

[[DISCUSSION]]

Is the client engaged in the conversation? Respond 'yes', 'no', or 'unclear'

[[RESPONSE]]
```




### `measurements`

A `measurement` is taken when the client is explicitly asked a question, or when other sensors are used to gather data about the client. Measurements are not part of the treatment definition, but are used to update `indicators` and `goals`.  Measurements are typed or at least have a constrained set of expected values.

For example, a measurement might be made by inserting a UI for a likert question into the chat window and asking: "How are you feeling right now?" on a 1-7 scale. 

Measurements are used to update `indicators` and `goals` in the system, and are stored in the database for later analysis. We might want to think about whether `measurements` and `indicators` are really distinct in this architecture. I think they are conceptually a bit different because an indicator can be a kind of latent measurement, generated by the system from the conversation or other sensors which are always on, whereas a measurement is a direct question asked of the client or a sensor reading taken as a snapshop. But in practice, I guess we might want to treat them the same way in the system?



### `actions`

`actions` are things the system does, but which are not directly related to the content of the conversation in turns. 

`actions` can be triggered by:

- transitions between steps
- hitting thresholds for `indicators` or `measurements`

Actions might include logging data, triggering the updating of `indicators` (e.g. 'check the client emotional arousal now'), or triggering `supervision` (e.g. inserting extra system messages to the therapist model), or triggering an `evaluation` by a human therapist.

Actions are a way to implement side effects from transitions or transition-evaluation. For example, on transitioning between steps, an action might summarise and store information in the patients' `notes` (a long-term store of information about treatment and progress in treatment).  To give a concrete example, when the client transitions past the 'elicit_imagery' step, the system might store the content of the imagery in the `notes` for later reference. This could be a summary of all the turns used to elicit and refine the imagery, and would make for efficient retrieval later.  

Another example might be actions which trigger a 'GOTO' to a special-case `step` in the DAG, or which triggers `supervision` to the therapist model and provides additional guidance or prompts for the therapy output llm.



### `supervision`

[this is probably not part of the MVP so we can consider later]

`supervision` is online coaching/support/guidance to the therapist llm. We'd want this to enable treatment developers to anticipate common failure modes or difficulties and provide additional guidance to the therapist model to get past them. Supervision prompts might be implemented as templated llm prompts which can access the conversation history and system state, and generate output that is only seen by the therapist model. For example, if the system detects that the client is not engaged, it might trigger a supervision prompt to the therapist model which says "Client does not seem engaged yet, try strategy X." or "Client does not seem engaged yet, keep trying.".

One use for `indicators` might be to implement these 'consitutional' or supervisory' models we discussed -- i.e., to track the progress of the therapy session against broader principles, or filter out dangerous responses from the patient or therapist. For example, we might have an `indicator` for 'client is asking for medical advice' which is updated continuously, and which could be used to trigger additional guidance/prompts to the therapist model, or to trigger an interrupt action which transitions the system into a special-case step (e.g. on in which the system explains that it can't offer medical advice). 



### `examples`

[this not necesarily part of the MVP so we can consider later]

Often, when defining `steps` or goals treatment developers will expect to be able to include examples for few-shot learning.

However, we won't always want to hard-code examples within the prompt itself. 

To make the system more dynamic and responsive to the conversation, we might want to store examples in a separate database and then retrieve them as needed using search/RAG type techniques.


To make it easy for treatment developers, it would be nice to use a similar text based format to define and access examples in prompts. This would end up similar to the syntax for  use for `notes` and `turns`.

To make examples available to the system, a TD might write a file like this:


```
------------
example: therapist asking permission to continue
tags: [permission, information-giving, alcohol]

CLIENT	Well, I usually drink when I'm at home trying to unwind and I drink while I'm watching a movie. And sometimes, um, I take a bath but I also drink when I take a bath sometimes.
THERAPIST	Okay. So, can I share with you some information on alcohol use?

------------
example: therapist asks an open question about relaxation and reflects answer
tags: [open-question, relaxation, reflection, repetition]

THERAPIST	What else besides drinking helps you relax and unwind in the evenings?
CLIENT	Well, I like to watch movies, read a book, and take a bath but sometimes I drink when I take a bath.
THERAPIST   So, it's not just wine that helps you relax. Um, there's reading a book, watching a movie, and taking a hot bath too.

```


In a `step` prompt, we might want to access "good examples" with a syntax like this:


`{examples:rag:"giving information", n_examples: 3}`


Or if we got really fancy we could specify what search strategy to use  like hyde (https://arxiv.org/abs/2212.10496) also see https://python.langchain.com/v0.1/docs/use_cases/query_analysis/techniques/hyde/

`{examples:"a therapist giving information about alcohol use", method: "hyde"}`

Here, the search string is used to generate 'hypothetical' examples which are then used to match against a corpus of known-good examples using cosine similarity. The `n_examples` parameter would limit the number of examples returned. 


It would be really neat if the search strings could be dynamic:

`{examples:"a therapist giving information about {problem_primary}", method: "hyde"}`

Here, the `problem_primary` note would be used to template the search string.


Another common/special case would be to just use the previous dialog to find examples that are similar to the recent client utterances:

`{examples, method:'turns', n:5}`

This would create a text string of the past 5 turns from the conversation and use cosine similarity to find similar interactions from good examples in the database. 



### `evaluations`

[this is not part of the MVP so we can consider later]

`evaluations` are judgements made by patients or human experts about individual `turns`, or sequences of `turns`.

3 examples of evaluations:

- the chatbot UI pops up a prompt separate from the main chat thread asking the user to evaluate the performance of the therapist on a scale of 1-5. This is a `measurement` (see above) but is used to capture data about the system performance. This evaluation is timestamped, so later we could use it to do things like RLHF on the therapist model turns. We could apply the rating to all turns within some (arbitrarily defined) window

- an (offline) evaluation is made by a human expert who reads the transcript of the conversation and rates the therapist on a quality scale, or a more in-depth set of questions which index the adherence of the therapy to the treatment manual. Here we might explicitly link the evaluation to a specific set of turns (e.g. pairs, triplets, quads of turns) or of even of longer sequences (like a whole session). One way to think about this kind of evaluation is as `measurements` taken from human experts whilst "replaying" the therapy session.

- an online or offline review of the performance of the therapist, triggered by an `action`



### `notes`

The system will naturally log all interactions between client and therapist, all measurements, actions etc and everything will be timestamped.

However, in defining the llm prompts for `steps` it's likely that we will want to use RAG and related memory techniques to include information from previous steps in the conversation. 

One option would be brute-force this and include large amounts of the previous conversation verbatim. However, it seems likely to me that this would be inefficient and would not scale well. It might also miss opporunities to use signal in the conversation history in a more sophisticated way.

For example, imagine a long series of turns/steps in which the client defines the problem they want to work on and their personal goals for behaviour change. This conversation might be quite long and complex, and include missteps or dead-ends. Rather than including it verbatim, we could create special summaries which would be more informative for the therapist model in later steps. 

For example this conversation shows how we might summarise notes from a single or multiple `steps`: https://chatgpt.com/share/67065e0a-3c48-8001-89fd-0d1c21af0358  We might save this in a note called `problem_primary`

In our llm prompt templating DSL we could have special tags like `{notes:*}` or `{notes:problem_primary}` or `{notes:problem_*}` to retrieve notes by name and insert them as system prompts into the context. 

We could also have search syntax like `{notes:"alcohol"}` for more RAG-like techniques which use semantic search. The tag might have other params like  `{notes:"barriers to change", n_tokens:300}`  would do something like

- do a semantic search for the string "barriers to change"
- limit the number of records to 50 most recent turns
- limit the number of tokens to be included to 300

And then those previous turns are dumped as a text string into the prompt for the therapist model. See the section on LLM prompting syntax below:



##### `formulations`

This is definitely not part of the initial product, but another possible use for `notes` is to create and update a `formulation` for a client which is essentially a summary of the client's problems, goals, and other relevant information. This could be used to provide a summary of the client's situation to the therapist model in later steps. 

----

Note for Ali - in clinician-speak, *clinical formulation* is a structured summary of a client's presenting problems, underlying psychological processes, and contributing factors, used to guide treatment. It tries to integrate information about the client’s history, current symptoms, and context (e.g., social, cognitive, emotional) to create a working hypothesis that explains the development and maintenance of their difficulties. Typically it includes key areas like the client's goals, strengths, challenges, and potential triggers or maintaining factors, and it helps therapists tailor interventions to the individual’s specific needs. it sin't the same as a diagnosis--- it is dynamic and can be revised as new information emerges during therapy, and it's not so concerned with putting people in specific diagnostic 'boxes' because they aren't necessarily helpful to formulating an individual treatment plan for that patient.

In FIT, we don't emphasise the concept of a formulation because it's not often delivered by psychologically trained staff (e.g. it will often be done by nurses) but it's a useful concept for the system to be able to use to provide context to the therapist model.




### `preferences`

Related to the idea of notes, we might want to split out the idea of client `preferences` from notes the therapist makes at run time.

Preferences might control things like:

- language
- assumed prior knowledge
- reading age and complexity of text the patient is comfortable with
- the level of detail in the therapist's responses 



# LLM prompting syntax using markdown/python string formatting

As we discussed, we need to define special syntax to allow the system to access the conversation history and other data sources to generate prompts for the therapist model.

We could use a markdown-like syntax for this, or some variant on python string formatting. 
I'm not bothered about the exact syntax provided it's not too hard to implment and isn't too ugly. I guess we also need to consider ease of writing and debugging when therapists are developing.



### `notes`

The special syntax `{notes:*}` allows us to access stored `notes` from previous steps.

We need to define how notes would be matched, either by name, topic/tag or content. But as possible examples: `{notes:problem}` might access a note with the name 'problem' and
`{notes:"alcohol"}` might access a note matching (e.g. via semantic search) the string 'alcohol' in the content. `{notes:*}` might access all the patient notes.



### `turns`

The special syntax `{turns:*}` would drop in all of the previous conversation history to the prompt.

`{turns:5}` would restrict to the past 5 turns, so something like:

```
CLIENT		Yes. What-what kind of health problems?
THERAPIST		Well things like heart disease, cancer, liver problems, uh, stomach pains, insomnia. Unfortunately, uh, people who drink at a risky level are more likely to be diagnosed with depression and alcohol can make depression worse or harder to treat.
CLIENT  	Hmm. Well, that's not good news.
THERAPIST   	Well, how do you think your drinking relates to the depression you've experienced?
CLIENT  	Well, to be honest, I drink sometimes when I'm feeling down and I find it more interesting and not so blur.
```



`{turns:steps:current}` would drop in all of the turns from the current step.

`{turns:steps:-1}` would drop in all of the turns from the last step.

`{turns:steps:[step_a, step_b]}` would include all turns from named steps

`{turns:*, n_tokens: 1000}` would only include the last 1000 tokens. This would be useful for keeping the prompt length down.


`{turns:rag:"barriers to change", n_tokens:300, n_turns:50, window:3}`  would do something like

- do a semantic search for the string "barriers to change"
- apply a window of 3 turns to the search (so, matches +/1 3 turns from the conversation)
- (probably) apply some de-duplication to the selected terns
- limit the number of records to 50 most recent turns
- limit the number of tokens to be included to 300


As a nice to have, summarising could be included within the rag template too, So `{turns:rag:"barriers to change", n_turns:50, max_tokens=300, window:3, summarise=true}`  would do something like

- do a semantic search for the string "barriers to change"
- limit the number of records to 50 most recent turns, with a window of 3 turns
- summarise the content of the turns to 300 tokens using a secondary llm call



### Metadata

Some system data would be exposed in all templates, e.g.:

- {meta: time_of_day} 
- {meta: client_name}
- {meta: client_location}
- {meta: client_age}
- {meta: n_turns_total}
- {meta: n_turns_this_step}



### Multistep prompting

The special syntax `[[FOO]]` would allow us to define a multi-step prompt where the model
responds to some output, and then incorporates this output with additional instructions to make a final response.  

This is useful because we can:

- make the therapist model discuss the inputs and do a chain-of-thought type response
- subsequently, summarise into a utterance suitable to return to the client

This should improve the quality of utterances, but also makes the system more 'introspectable'. In my experience being able to inspect the 'reasoning' first helps expert observers understand what it is responding to in the prompt data and how it is generating the output. We can save these 'private thoughts' in the database for later analysis, and use them to improve the system.


A simple example:

```
You are a  therapist treating a patient for {notes:problem_primary}.
The client has recently said this:

{turns:10}

Consider several possible interpretations of what they are saying. Think about how you might respond to this in accordance with MI principles. 

[[DISCUSSION]]


Now, think of several different topics for open questions which would be suitable to raise at this point:

[[TOPICS]]


Now, summarise this into a single response for the client. You need to say something that fits nearly into the existing conversation and is not too complex. 
Always be polite, empathetic and professional.

{turns:2}

THERAPIST: [[NEXT_UTTERANCE]]

```



### Includes/inheritance  within templates

Note that the final part of this prompt described in the multistep prompting section might be 'inherited' from a standard "make the next move" template for stylistic consistency. 

E.g. we could define a standard output prompt like this:


```{#make_next_utterance}
Now, summarise this thinking into a single response for the client. 
You need to say something that fits nearly into the existing conversation 
and is not too complex.  Always be polite, empathetic and professional.

{turns:n_turns}

THERAPIST: [[NEXT_UTTERANCE]]
```

And then in the main prompt we could just include this with a reference to the id of the template:

```
[...]

Brainstorm ideas for the best course of action:

[[DISCUSSION]]

{include:#make_next_utterance, n_turns=2}
```

Using includes/inheritance like this could simplify prompts for individual steps.



### Worked example

In the `step` "elicit_imagery" we might have a prompt like:

```
You are a FIT therapist [etc etc].

You are in the middle of a treatment session and have got to know your clients' problem and their goals for therapy. You have been discussing their problem with them for a while now. 

- The client's primary problem is: {notes:primary_problem}
- The client's name is: {notes:client_name}

Here is a summary of what they have said about their problem so far: 

{notes:problem_summary}

Now, you want to elicit an image of the problem from the client. You might say something like   

> 'Can you imagine yourself in the situation you've been describing? What do you see, hear, feel?'


These are other examples of dialog which worked for you in the past:

`{examples:"a therapist asking a client to generate imagery related to {problem_primary}", method: "hyde"}`


Refer to the specific problem the client is facing here though. Make sure to personalise your suggestion for them and their specific case.

Think about this step by step and consider all of the information above to guide your response.  Be full in your discussion of what the best course of action would be.

[[DISCUSSION]]

{include:#make_next_utterance, n_turns=2}

```



### Using markdown for actions and goals?

We could also use markdown for defining actions, goals, transition, etc but haven't thought in detail about this yet.

One simple example might be an action to save a `note` when transitioning between steps.
So, for a given transition we might define a `summarise-step` action like this:


```
You are a therapist
Below is a transcript of a conversation with your client {notes:client_name}.
They are working on: {notes:problem_primary}

This is your recent conversation:

{turns:current_step}


# Your task now

You want to make notes for later, summarising what was said
focus on:

- any problems identified
- any potential barriers
- any potential solutions

Write in the first person, past tense. 
Don't include a preamble. 
Refer to the client as {notes:client_name}.


[[problems_exploration]]

Now write a very short one line summary of your summary

[[problems_exploration_summary]]

```

Note that this would save 2 notes under the names `problems_exploration` and `problems_exploration_summary` respectively, which we could refer to later on.


An example of this sort of prompt is here: https://chatgpt.com/share/670672cd-7c54-8001-9bd4-883e9b8672be



# Defining the DAG and transition dependencies

We need a format (perhaps yaml because easier to read than json?) to define the connections in the DAG. Ultimately this might need a GUI, but not now.

Maybe it would look something like below. 

```yaml
nodes: 
    establish_rapport:
        # specify which other nodes we can transition-to, and dependencies/pre-requisites
        transitions: 
            - eliciting_problem:
                dependencies: [client_wants_to_change]
        # specify which notes templates to use on transition
        take_notes: [general, summarise_rapport] 
                
    eliciting_problem:
        transitions:
            - elicit_imagery:
                dependencies: [simple_problem_identified]
                measurements: [client_ok]
            - break_down_problem:
                dependencies: [problem_too_complex]
        take_notes: [problem_primary, problem_summary]
        

    break_down_problem:
        transitions:
            - elicit_imagery:
                dependencies: [simple_problem_identified]
        take_notes: [problem_primary, problem_others, problem_summary]

    elicit_imagery:
        # ... more steps defined

indicators:
    - emotional_arousal:
        # update assessment on every turn
        update: turn
    - client_engaged_in_therapy:
        # only update on transitions between steps
        update: step

```


In this example:

- `establish_rapport` is a `step` in the DAG, and we define the transitions from this step to other steps in the DAG.

- `summarise_rapport` is the name of a `note` template which is made/saved when the transition away from `establish_rapport` is made. Similarly, `problem_primary` is a note template applied when transitioning from `eliciting_problem` to another step.

- `simple_problem_identified` would be the name of a goal which is a pre-requisite to transition away from `eliciting_problem`. If this goal is not met, the transition would not be allowed.

- `client_ok` is the name of a `measurement` we will take on the transition away from the `eliciting_problem` to the `elicit_imagery` step. This measurement might simply be a UI element which asks  client to press a button marked "OK"  or "Not OK" to continue. Or it could be a 1-7 scaled question.




### Validating the DAG and dependencies defined within it

[not part of the MVP]

We should probably define a set of rules for the DAG which would be checked before the system is run.

For example, we could know ahead of time if the DAG creates dead ends and should warn the treatment developer.

We could also know if a template will be used within a context where notes/variables it references are not going to be available (although this seems a much harder problem to catch).

We will probably need to expend some effort to make sure templating errors (e.g. syntax errors or missing prompts/notes/data) are caught before the system is run or logged at tun time. This might be a bit tricky because the templating system is quite flexible and we might not know all the possible errors ahead of time. But we could at least catch some of the more obvious ones and give helpful feedback to treatment developers.



### Generating a `review` of progress?

[Not part of the MVP]

Sometimes we might want to summarise where the client is at within the intervention, taking into account all the metadata and notes we have stored.

A `review` is conceptually similar to a `note`, but is generated by the system on demand rather than saved in a transition or other action. 

A review might be a summary of the conversation, of the goals achieved and include information about indicators. 

A `review` could be used for human review of the system performance, or for generating a summary of the session for the client.

A review could be templated in the same way as a note:


```
{notes:client_name} is currently working on {notes:problem_primary} 
as part of their therapy.

This is their entire conversation so far:

{turns:*}

## Summaries of the conversation

{notes:client_name} is currently working on {notes:problem_primary} 
as part of their therapy.

The therapist has made the folling notes:

{notes:*}


## Goals

They have achieved the following goals: {goals:achieved}

They have not yet achieved the following goals: {goals:unachieved}


## Other data

The following indicator data is available: 

{indicators:active}



# Your task now

Summarise the progress this client has made so far in therapy.

Write a short summary of the conversation and the goals achieved so far suitable to send to the client in an email.//
Write a short summary of the conversation and the goals achieved so far suitable to send to their GP//
Write a short summary of the conversation and the goals achieved so far to help researchers understand how well they are doing in therapy.
```




# User interfaces

[not all of this in MVP]

The system presents different interfaces for:

- the client: via chat, and through simple UI elements like buttons or sliders for `measurements`

- supervisors: via a web interface which allows them to see the conversation history and provide evalutions on the quality of the conversation. Or perhaps also to manually add notes and hints to be included in system llm prompts.

- the intervention developer: 
    - via a web interface or API which allows them to update the primitives described above, see the conversation histories, and also see stats on the performance of the system, e.g. how many goals were achieved, how many transitions were made, etc, time to achieve transitions etc.
    - via sandbox chat with the system to test the system in real time, and to see how the system is responding to prompts. This could be useful for debugging and for understanding how the system is working in real time. This sandbox view would allow intervention developers to create a 'session' and tweak the system in real time to see how it responds. E.g. they could edit the content of notes, or the content of the conversation history, or the state of goals, and then 'jump' the current position of the bot in the DAG.

- the system developer: again some web interface + DB access and logging and log analysis.






# Other relevant work and software

TBC

It struck me in places this is a bit like a workflow engine, and I wondered if things lkike Prefect https://github.com/PrefectHQ/prefect or  luigi could be useful here. https://github.com/spotify/luigi   Prefect in particular seems like a good fit, but I haven't used it before