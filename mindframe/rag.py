"""
Functions to

- embed text in a document store
- extract chunks of the original text for RAG prompting


Examples:


from mindframe.rag import rag_examples, hyde_examples, embed_examples

print( rag_examples("a client talking about anxiety"),
hyde_examples("a client talking about anxiety"))


embed_examples(examples=Example.objects.all())


"""

import logging
import os

from haystack import Document, Pipeline
from haystack.components.preprocessors import DocumentSplitter
from haystack_integrations.document_stores.pgvector import PgvectorDocumentStore
from haystack_integrations.components.retrievers.pgvector import PgvectorEmbeddingRetriever
from haystack.components.builders import PromptBuilder
from haystack_integrations.components.generators.ollama import OllamaGenerator
from haystack.components.converters import OutputAdapter

from haystack import component
from haystack.components.embedders import AzureOpenAITextEmbedder, AzureOpenAIDocumentEmbedder
from haystack.components.generators import AzureOpenAIGenerator

# from haystack_integrations.components.embedders.ollama import (
#     OllamaDocumentEmbedder,
#     OllamaTextEmbedder,
# )

from haystack.document_stores.types import DuplicatePolicy
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.retrievers import SentenceWindowRetriever

from haystack import tracing
from typing import List, Optional
from haystack.tracing.logging_tracer import LoggingTracer

from mindframe.models import TreatmentSession, Example

# from mindframe.settings import OLLAMA_URL

from django.conf import settings

from haystack.utils import Secret

logger = logging.getLogger(__name__)

if settings.DEBUG and False:
    logging.basicConfig(format="%(levelname)s - %(name)s -  %(message)s", level=logging.WARNING)
    logging.getLogger("haystack").setLevel(logging.DEBUG)

    tracing.tracer.is_content_tracing_enabled = (
        True  # to enable tracing/logging content (inputs/outputs)
    )
    tracing.enable_tracing(
        LoggingTracer(
            tags_color_strings={
                "haystack.component.input": "\x1b[1;31m",
                "haystack.component.name": "\x1b[1;34m",
            }
        )
    )


doc_store = PgvectorDocumentStore(
    connection_string=Secret.from_token(settings.DATABASE_URL),
    embedding_dimension=1024,
    vector_function="cosine_similarity",
    search_strategy="hnsw",
    recreate_table=False,
)


def embed_examples(examples):
    doc_splitter = DocumentSplitter(split_by="sentence", split_length=2, split_overlap=1)
    # doc_embedder = OllamaDocumentEmbedder(model="nomic-embed-text", url=OLLAMA_URL)
    doc_embedder = AzureOpenAIDocumentEmbedder(
        dimensions=1024,
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        api_key=Secret.from_token(os.environ.get("AZURE_OPENAI_API_KEY")),
        azure_deployment="text-embedding-3-large",
    )
    docs = [
        Document(
            content=i.text,
            meta={
                "id": i.id,
                "intervention": i.intervention.id,
                "content_type": "mindframe.Example",
            },
        )
        for i in examples
    ]

    chunks = doc_splitter.run(documents=docs)
    chunks_embedded = doc_embedder.run(chunks["documents"])
    doc_store.write_documents(chunks_embedded.get("documents"), policy=DuplicatePolicy.OVERWRITE)


# SIMPLE RAG


def rag_pipeline():
    rag = Pipeline()
    # rag.add_component("text_embedder", OllamaTextEmbedder(model="nomic-embed-text", url=OLLAMA_URL))
    rag.add_component(
        "text_embedder",
        AzureOpenAITextEmbedder(
            dimensions=1024,
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
            api_key=Secret.from_token(os.environ.get("AZURE_OPENAI_API_KEY")),
            azure_deployment="text-embedding-3-large",
        ),
    )
    rag.add_component("retriever", PgvectorEmbeddingRetriever(document_store=doc_store))
    rag.add_component(
        "window_retriever", SentenceWindowRetriever(document_store=doc_store, window_size=1)
    )
    rag.connect("text_embedder.embedding", "retriever.query_embedding")
    rag.connect("retriever", "window_retriever")
    return rag


# CRUDE IMPLEMENTATION OF HYDE


def hyde_pipeline():
    hyde = Pipeline()
    hyde.add_component("hyde_prompt", PromptBuilder(template=""))

    # TODO: enable user to specify model/provider
    # hyde.add_component("llm", OllamaGenerator(model="llama3.2", url=OLLAMA_URL))
    hyde.add_component(
        "llm",
        AzureOpenAIGenerator(
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
            api_key=Secret.from_token(os.environ.get("AZURE_OPENAI_API_KEY")),
            # TODO allow user to specify hyde model
            azure_deployment="gpt-4o-mini",
        ),
    )

    # hyde.add_component(
    #     "query_embedder", OllamaTextEmbedder(model="nomic-embed-text", url=OLLAMA_URL)
    # )
    hyde.add_component(
        "query_embedder",
        AzureOpenAITextEmbedder(
            dimensions=1024,
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
            api_key=Secret.from_token(os.environ.get("AZURE_OPENAI_API_KEY")),
            azure_deployment="text-embedding-3-large",
        ),
    )
    hyde.add_component("llm_first", OutputAdapter(template="{{ replies[0] }}", output_type=str))

    hyde.add_component("retriever", PgvectorEmbeddingRetriever(document_store=doc_store))
    hyde.add_component(
        "window_retriever", SentenceWindowRetriever(document_store=doc_store, window_size=1)
    )

    hyde.connect("hyde_prompt.prompt", "llm")
    hyde.connect("llm.replies", "llm_first")
    hyde.connect("llm_first", "query_embedder")
    hyde.connect("query_embedder.embedding", "retriever.query_embedding")
    hyde.connect("retriever", "window_retriever")

    return hyde


# Functions to call to get strings for templates


def rag_examples(query, top_k=3, window_size=2, similarity_threshold=0.2, interventions=None):
    """
    Extract semantically similar chunks/examples from the Example model

    Args:
    - question: str
    - top_k: int (number of examples to return)
    - window_size: int (number of sentences to return around the matched sentence)
    - similarity_threshold: float (minimum similarity to return) NOT IMPLEMENTED YET: TODO
    """

    rag = rag_pipeline()
    # construct filters for the intervention
    if interventions:
        filters = {
            "field": "meta.intervention",
            "operator": "in",
            "value": [i.id for i in interventions],
        }
    else:
        filters = {}

    results = rag.run(
        {
            "text_embedder": {"text": query},
            "retriever": {"top_k": top_k, "filters": filters},
            "window_retriever": {"window_size": window_size},
        }
    )
    return results["window_retriever"]["context_windows"]


def hyde_examples(
    query,
    top_k=2,
    window_size=2,
    hyde_prompt_template="Imagine a client/therapist are talking. We need to simulate some text of their dialogue. The topic/example should be of: \n{text}.\n\nSimulate some realistic dialogue. No more than 3 utterances.",
    interventions=None,
):
    """
    Use Hypothetical Document Embedding (HyDE) to generate examples of text based on a prompt.
    This may be better when we can specify the topic/scenario of the examples we'd like.
    """

    hyde = hyde_pipeline()
    # construct filters for the intervention
    if interventions:
        filters = {
            "field": "meta.intervention",
            "operator": "in",
            "value": list(interventions.values_list("id", flat=True)),
        }
    else:
        filters = {}

    results = hyde.run(
        {
            "hyde_prompt": {
                "template": hyde_prompt_template.format(text=query),
                "template_variables": {"text": query},
            },
            "retriever": {"top_k": top_k, "filters": filters},
            "window_retriever": {"window_size": window_size},
        },
        include_outputs_from={"llm_first"},
    )
    logger.info(f"Hypothetical document embedded and used for search:\n\n {results['llm_first']}")

    return results["window_retriever"]["context_windows"]
