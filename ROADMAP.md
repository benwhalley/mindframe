
- budgets for bot conversations? 50 max turns?
- allow public interactions?
- catch errors related to budget overruns

https://docs.litellm.ai/docs/proxy/users
{
  "detail":"Authentication Error, ExceededTokenBudget: Current spend for token: 7.2e-05; Max Budget for Token: 2e-07"
}



# Research ideas

Long term qual interviews
Maintenance tools between sessions
Maintenance after intervention ends
Reduce contact points in group interventions?


# Roadmap for `mindframe` development


Test async version of webhook and chat UI


ComputedData
Allow summarisation or computations on existing notes, and these to be available in prompt context or dashboards
Plugin architecture for the code components of this? E.g. a function on the data


InterventionDashboard
Define what metrics to show in the dashboard for an intervention, persumably across conversations.
Use a plugin architecture for this, so that new metrics can be added easily?
Also new display functions?





use chatgpt to ask for similarity judgement between two texts for alignment with high quality original text??



/end
(kills all scheduled nudges)


/info
/undo -




Matrix bot:





## User engagement/maintenance

Mark special steps as 'Nudges'
These are not part of the main DAG, but still have a prompt and access to history.
An intervention can define rules/schedules for when a check-in is needed.
A check in step could also define preconditions for the check-in to be triggered, via a judgement.

When triggered, a response is made using the check-in prompt.
The user responds in the normal conversation flow.



## Improved turn taking and picking the right speaker

- tests for this


## Group conversations and group processes?

TBC


## Interaction with external systems

- start a conversation with context from an external system
- allows creating a new conversation and posting to it to create notes
- then can start interacting with the conversation in the normal way, given special prompts




# "Experiments"

create a pool of transcripts
set parameters for how to select sequences from them
create simluations for completions of sequences with different models
text embeddings of the results and export to analyse





## RAG and context enhancement

Problems to solve:

1. How to chunk our data for optimal embedding and retrieval for generation.

2.  How to give treatment developers good and easy to use control over what gets included in a template: Both through the syntax in templates, and techniques like HyDE which might improve the quality of matching. Is caching also a part of this.


## User and data management
- magic links to start a new cycle/session - make sure they are safe


## Performance metrics


##### Synthetic data + semantic similarity with established datasets

Generate synthetic data, then use semantic similarity with high-quality vs low-quality MI in the AnnoMI dataset. E.g.:

- Embed each utterance in annomi
- For each Turn, calculate embedding
- Find similarity score between each Turn and closest match in annomi high quality Repeat for low quality utterances in annomi.

We expect similarity with high-quality to be higher than for low quality. This gap should grow over time.




## Training data and fine tuning

As we use the system, it would be nice to be able to mark Judgements and Turns as being particularly good or bad examples of their type. This could be used to fine tune the model.
We could potentially integrate some fine-tuning tools into the admin UI itself. I.e. a django admin UI which allows the user to mark data as high quality and suitable for tuning, then a django management comment which build a new set of model weights and installs them so they are available for subseuqent runs.



## Performance


### Use of simpler models for Judgements

Some models are very simple classifiers and don't need ChatGPT 4. We should think about how to implement this switching between models. Probably just a field on the Judgement record.



### Queuing and scheduling


When a Bot user sends multiple messages in a row, the bot will process each in turn using celery. This might be wasteful... it could be better to kill existing tasks when recieving new input? Keep a key/lock/semaphore on the conversation model?



----
At present, when we add Judements to step all are run against the LLM before
the transition is evaluated.

This is potentially slower than needed, because not all Judgements are going to be needed to evaluate the transition.

We should be able to queue the Judgements and only run the ones that are needed. We should also be able to make transition evaluation async? Perhaps we can set all the Judgements to run in parallel and then check for transitions as they complete and become available?

We could use celery/redis to queue tasks. More complex is thinking about the






# Localisation

Localising datetimes: e.g. currently set to London/Europe, but if we had Swedish users then timezones would be out for nudges etc.
