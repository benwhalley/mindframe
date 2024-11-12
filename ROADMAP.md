# Roadmap for `mindframe` development


- magic links to start a new cycle/session - make sure they are safe



## RAG and context enhancement

Problems to solve:

1. How to chunk our data for optimal embedding and retrieval for generation.

2.  How to give treatment developers good and easy to use control over what gets included in a template: Both through the syntax in templates, and techniques like HyDE which might improve the quality of matching. Is caching also a part of this.



## Training data and fine tuning

As we use the system, it would be nice to be able to mark Judgements and Turns as being particularly good or bad examples of their type. This could be used to fine tune the model.
We could potentially integrate some fine-tuning tools into the admin UI itself. I.e. a django admin UI which allows the user to mark data as high quality and suitable for tuning, then a django management comment which build a new set of model weights and installs them so they are available for subseuqent runs.



## Performance


### Use of simpler models for Judgements

Some models are very simple classifiers and don't need ChatGPT 4. We should think about how to implement this switching between models. Probably just a field on the Judgement record.



### Queuing and scheduling

At present, when we add Judements to step all are run against the LLM before
the transition is evaluated.

This is potentially slower than needed, because not all Judgements are going to be needed to evaluate the transition.

We should be able to queue the Judgements and only run the ones that are needed. We should also be able to make transition evaluation async? Perhaps we can set all the Judgements to run in parallel and then check for transitions as they complete and become available?

We could use celery/redis to queue tasks. More complex is thinking about the
