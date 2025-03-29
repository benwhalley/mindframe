---
layout: default
title: About Mindframe
---

# About MindFrame

> Mindframe is an integrated system for treatment developers and service managers to deliver Conversational AI tools.

MindFrame makes it possible to implement psychologically informed chatbots built on large language models (LLMs), capable of high-quality individual and group intervention. The system is designed to be introspectable, verifiable, and adaptable to complex interventions and varied clinical settings.

Mindframe coordinates multiple AI models, orchestrating their outputs into coherent, structured, conversations with clients. The system allows intervention developers to define sessions as directed graphs, with nodes representing different stages of the intervention. Complex interventions can be broken-down into smaller, more manageable components for development, testing and refinement, and the system can track client progress and adjust interventions based on historical data.

Using a graph-based representation of interventions, MindFrame allows for more control over the treatment flow, and for services to be more easily validated against guidelines and best practice, tested for efficacy, and refined to suit the local context. Mindframe is not a 'black box': it is designed to ensure that services are grounded in psychological theory, are evidence-based, and can be properly supervised and audited by human clinicians.

---

For developers looking to setup a local instance of mindframe, see: [this page](docs/development.md)


### Key Features

- *Modular Structure*: Allows intervention developers to break down complex interventions into smaller components, making it easier to test and validate individual parts of an intervention.

- *Client Tracking*: A database maintains a history of each client’s progression, including conversation history, and a record of internal (system) judgements, notes, and other session information.

- *Collaboration*: Mindframe uses simple text-based templates to define an intervetion in terms of steps, transitions, judgements, notes, and actions. Each part of the intervention can be revised and reviewed by the intervention developer in consultation with clinicians.

- *Adaptable*: Interventions can be tailored to particular client groups or local context; retrieval augmented generation allows clinicians and managers to incorporate their own examples, case studies, and local knowledge.

- *Theory-Led*: Mindframe is designed to ensure that interventions are grounded in psychological theory and are evidence-based. Although AI is used to interact with clients, the design ensures that the service follows intervention manuals and guidelines, and is transparent and verifiable.

- *Safety and Verification*: Human supervisors or therapists will oversee interactions in real time, providing an extra layer of safety and ensuring that the models are operating as expected.


### Graph-based interventions

Mindframe is different from other chatbot systems — especially those based on fine-tuning with large datasets — because it represents therapy as a _directed graph_ of interactions. This allows for complex interventions to be broken down into smaller, more manageable components, and for the system to track client progress and adjust interventions based on historical data.  Defining interventions in this way also makes the system more flexible, and rapidly adaptable to new research, or to local guidelines and requirements.

Unlike systems which fine-tune language models to produce output similar in tone of style to that of a therapist, mindframe focusses on the structure of the therapy itself. This allows for more control over the therapy flow, and for interventions to be more easily validated and tested.

Segmentation of different tasks allows treatment developers to integrate multiple specialised models trained in different tasks: for example different models may be used to detect transitions in conversation between stages of therapy, versus generating realistic text/speech. This helps to reduce the load on any single model, reduces hallucination, and ensures the language model follows the larger structural transitions within and across sessions. The modular nature of the system allows for easy testing and validation of individual intervention components.



### A shared language to describe interventions

![](docs/steps.png)


MindFrame organizes therapy sessions around several key primitives:

- *Steps* are the core units of the intervention, typically represented as a single LLM prompt and its associated actions.

- *Transitions*: Define pathways between steps and the conditions required to move from one step to the next.

- *Turns* are the basic unit of interaction between the client and the system and together form a *Conversation*. In regular use a Conversation is simple sequence of Turns, but the system stores Turns as nodes in a tree structure. At any turn in a Conversation a branch can be made, representing alternative paths the conversation could have taken (for example, during simulations using a synthetic client, or when collating multiple alternative human-generated completions). Each Turn is associated with a Step.

- *Judgements* are structured evaluations of the client state based on conversation history and other stored data. Judgements are used to determine the timing of transitions between steps, or to log progress against pre-defined goals.

- *Notes* allow summaries of conversation history to be saved as unstructured text — for example as clinical notes — providing context used in later generation steps, or to help human supervisors track clients' progress through an intervention.

- *Questions* are prompts that solicit structured input from the client (e.g. mood ratings, or other measures of outcome).

- *Examples* are short excepts from good or bad therapeutic practice, stored for semantic search and retrieval during conversations. Steps are templated in a way that allows treatment developers to dynamically insert relevant examples into the LLM prompt, leveraging the power of recent AI models to use 'few-shot' learning to generate high-quality responses.

Each of these components is defined in a simple, declarative text-based format. See [examples of the syntax here](docs/syntax.md).
