# -*- coding: utf-8 -*-
from setuptools import setup

packages = \
['mindframe',
 'mindframe.management.commands',
 'mindframe.migrations',
 'mindframe.templatetags',
 'mindframe.tests']

package_data = \
{'': ['*'],
 'mindframe': ['fixtures/*',
               'static/mindframe/css/*',
               'static/mindframe/js/*',
               'templates/*',
               'templates/admin/*',
               'templates/admin/mindframe/intervention/*']}

install_requires = \
['Django>=5.0.6,<6.0.0',
 'black>=24.4.2,<25.0.0',
 'boto3>=1.34.119,<2.0.0',
 'celery>=5.4.0,<6.0.0',
 'colorlog>=6.9.0,<7.0.0',
 'crispy-bootstrap5>=2024.10,<2025.0',
 'dj-database-url>=2.1.0,<3.0.0',
 'django-autoslug>=1.9.9,<2.0.0',
 'django-compressor>=4.4,<5.0',
 'django-crispy-forms>=2.3,<3.0',
 'django-debug-toolbar>=4.4.2,<5.0.0',
 'django-environ>=0.11.2,<0.12.0',
 'django-extensions>=3.2.3,<4.0.0',
 'django-hijack>=3.5.1,<4.0.0',
 'django-lifecycle>=1.2.4,<2.0.0',
 'django-magiclink @ git+https://github.com/benwhalley/django-magiclink.git',
 'django-shortuuidfield>=0.1.3,<0.2.0',
 'django-storages>=1.14.3,<2.0.0',
 'djmail>=2.0.0,<3.0.0',
 'gradio>=5.5.0,<6.0.0',
 'haystack-ai>=2.9.0,<3.0.0',
 'haystack-experimental==0.3.0',
 'instructor>=1.6.4,<2.0.0',
 'ipython>=8.29.0,<9.0.0',
 'langchain>=0.3.11,<0.4.0',
 'langfuse>=2.56.1,<3.0.0',
 'ollama-haystack>=2.0.0,<3.0.0',
 'pandoc>=2.4,<3.0',
 'pgvector',
 'pgvector-haystack>=1.2.0,<2.0.0',
 'poetry-plugin-export>=1.8.0,<2.0.0',
 'pydantic>=2.9.2,<3.0.0',
 'python-box>=7.2.0,<8.0.0',
 'python-decouple>=3.8,<4.0',
 'python-dotenv>=1.0.1,<2.0.0',
 'python-magic>=0.4.27,<0.5.0',
 'redis>=5.2,<6.0',
 'ruamel-yaml>=0.18.6,<0.19.0',
 'rules>=3.4,<4.0',
 'setuptools',
 'shortuuid>=1.0.13,<2.0.0',
 'tiktoken>=0.8.0,<0.9.0',
 'uvicorn>=0.30.1,<0.31.0',
 'watchdog>=4.0.1,<5.0.0',
 'werkzeug>=3.0.3,<4.0.0',
 'whitenoise>=6.6.0,<7.0.0']

extras_require = \
{':sys_platform == "darwin"': ['psycopg2_binary>=2.9,<3.0'],
 ':sys_platform == "linux"': ['psycopg2>=2.9,<3.0']}

entry_points = \
{'console_scripts': ['mindframe-bot = mindframe.chatbot:main']}

setup_kwargs = {
    'name': 'mindframe',
    'version': '0.1.20',
    'description': 'A Python package for the `mindframe` project',
    'long_description': "# Mindframe\n\nMindFrame is a Python package designed to help treatment developers implement psychologically informed chatbots that leverage the power of large language models (LLMs) to generate high-quality individual and group interventions. The system is developed to remain introspectable, verifiable, and adaptable to complex interventions.\n\nMindFrame coordinates multiple models, orchestrating their outputs into coherent, structured, conversations with clients. The system allows intervention developers to define sessions as directed graphs, with nodes representing different stages of the intervention. Complex interventions can be broken-down into smaller, more manageable components for development, testing and refinement, and the system can track client progress and adjust interventions based on historical data.\n\nUsing a graph-based representation of interventions, MindFrame allows for more control over the treatment flow, and for services to be more easily validated against guidelines and best pratice, tested for efficacy, and refined to suit the local context. Mindframe is not a 'black box': it is designed to ensure that services are grounded in psychological theory, are evidence-based, and can be properly supervised and audited by human clinicians.\n\n\n---\n\nFor developers looking to setup a local instance of mindframe, see: [this page](development.md)\n\n### Key Features\n\n- *Modular Structure*: Allows intervetion developers to break down complex interventions into smaller components, making it easier to test and validate individual parts of an intervention.\n\n- *Client Tracking*: A database maintains a history of each client’s progression, including conversation history, and a record of internal (system) judgements, notes, and other session information.\n\n- *Collaboation*: Mindframe uses simple text-based templates to define an intervetion in terms of steps, transitions, judgements, notes, and actions. Each part of the intervention can be revised and reviewed by the intervention developer in consultation with clinicians.\n\n- *Adaptable*: Interventions can be tailored to particular client groups or local context; retrieval augmented generation allows clinicians and managers to incorporate their own examples, case studies, and local knowledge.\n\n- *Theory-Led*: Mindframe is designed to ensure that interventions are grounded in psychological theory and are evidence-based. Although AI is used to interact with clients, the design ensures that the service follows intervention manuals and guidelines, and is transparent and verifiable.\n\n- *Safety and Verification*: Human supervisors or therapists will oversee interactions in real time, providing an extra layer of safety and ensuring that the models are operating as expected.\n\n\n### Graph-based interventions\n\nWhat makes mindframe different from other chatbot systems based on fine-tuning with large datasets is its ability to represent therapy as a directed graph. This allows for complex interventions to be broken down into smaller, more manageable components, and for the system to track client progress and adjust interventions based on historical data.  Defining interventions in this way also makes the system more flexible, and rapidly adaptable to new research, or to local guidelines and requirements.\n\nUnlike systems which fine-tune language models to produce output similar in tone of style to that of a therapist, mindframe focusses on the structure of the therapy itself. This allows for more control over the therapy flow, and for interventions to be more easily validated and tested.\n\nSegmentation of different tasks allows treatment developers to integrate multiple specialised models trained in different tasks: for example different models may be used to detect transitions in conversation betwee stages of therapy, versus generating realistic text/speech. This helps to reduce the load on any single model, reduces hallucination, and ensures the language model follows the larger structural transitions within and across sessions. The modular nature of the system allows for easy testing and validation of individual intervention components.\n\n\n\n### A shared language to describe interventions\n\n![](docs/steps.png)\n\n\nMindFrame organizes therapy sessions around several key primitives:\n\n- *Steps* are the core units of the intervention, typically represented as a single LLM prompt and its associated actions.\n\n- *Transitions*: Define pathways between steps and the conditions required to move from one step to the next.\n\n- *Turns* are the basic unit of interaction between the client and the system. A conversation is made up of multiple turns, each of which is associated with a step.\n\n- *Judgements* are structured evaluations of the client state based on conversation history and other stored data. Judgements are used to determine the timing of transitions between steps, or to log progress against pre-defined goals.\n\n- *Notes* allow summaries of conversation history to be saved as unstructured text — for example as clinical notes\xa0— providing context used in later generation steps, or to help human supervisors track clients' progress through an intervetion.\n\n- *Questions* are prompts that solicit structured input from the client (e.g. mood ratings, or other measures of outcome).\n\n- *Examples* are short excepts from good or bad therapeutic practice, stored for semantic search and retrieval during conversations. Steps are templated in a way that allows treatment developers to dynamically insert relevant examples into the LLM prompt, leveraging the power of recent AI models to use 'few-shot' learning to generate high-quality responses.\n\nEach of these components is defined in a simple, declarative text-based format. See [examples of the syntax here](docs/syntax.md).\n",
    'author': 'Ben Whalley',
    'author_email': 'ben.whalley@plymouth.ac.uk',
    'maintainer': 'None',
    'maintainer_email': 'None',
    'url': 'None',
    'packages': packages,
    'package_data': package_data,
    'install_requires': install_requires,
    'extras_require': extras_require,
    'entry_points': entry_points,
    'python_requires': '>=3.11,<3.13',
}


setup(**setup_kwargs)

