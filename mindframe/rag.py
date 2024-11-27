import logging
import os

from haystack import Document, Pipeline
from haystack.components.preprocessors import DocumentSplitter
from haystack_integrations.document_stores.pgvector import PgvectorDocumentStore
from haystack_integrations.components.retrievers.pgvector import PgvectorEmbeddingRetriever
from haystack.components.builders import PromptBuilder
from haystack_integrations.components.generators.ollama import OllamaGenerator
from haystack import component

from haystack_integrations.components.embedders.ollama import (
    OllamaDocumentEmbedder,
    OllamaTextEmbedder,
)

from haystack.document_stores.types import DuplicatePolicy
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.retrievers import SentenceWindowRetriever

from haystack import tracing
from typing import List, Optional
from haystack.tracing.logging_tracer import LoggingTracer

from mindframe.templatetags.turns import format_turns
from mindframe.models import TreatmentSession, Example
from mindframe.settings import OLLAMA_URL

from django.conf import settings

from haystack.utils import Secret

if settings.DEBUG:
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
    embedding_dimension=768,
    vector_function="cosine_similarity",
    search_strategy="hnsw",
    recreate_table=False,
)

doc_splitter = DocumentSplitter(split_by="sentence", split_length=2, split_overlap=1)
doc_embedder = OllamaDocumentEmbedder(model="nomic-embed-text", url=OLLAMA_URL)


def embed_examples(examples):
    docs = [
        Document(
            content=i.text,
            meta={
                "id": i.id,
                "intervention": i.intervention.id,
                "content_type": "mindframe.Example",
            },
        )
        for i in examples  # format_turns(i.turns.all())
    ]

    chunks = doc_splitter.run(documents=docs)
    chunks_embedded = doc_embedder.run(chunks["documents"])
    doc_store.write_documents(chunks_embedded.get("documents"), policy=DuplicatePolicy.OVERWRITE)


# embed_examples(examples=[Example.objects.all().last()])

# SIMPLE RAG


def rag_pipeline():
    rag = Pipeline()
    rag.add_component("text_embedder", OllamaTextEmbedder(model="nomic-embed-text", url=OLLAMA_URL))
    rag.add_component("retriever", PgvectorEmbeddingRetriever(document_store=doc_store))
    rag.add_component(
        "window_retriever", SentenceWindowRetriever(document_store=doc_store, window_size=1)
    )
    rag.connect("text_embedder.embedding", "retriever.query_embedding")
    rag.connect("retriever", "window_retriever")
    return rag


# CRUDE IMPLEMENTATION OF HYDE


@component
class GetFirstLLMReply:
    @component.output_types(text=str)
    def run(self, replies: List[str]):
        return {"text": replies[0]}


def hyde_pipeline():
    hyde = Pipeline()
    hyde.add_component("hyde_prompt", PromptBuilder(template=""))
    hyde.add_component("llm", OllamaGenerator(model="llama3.2", url=OLLAMA_URL))
    hyde.add_component("llm_first", GetFirstLLMReply())
    hyde.add_component(
        "query_embedder", OllamaTextEmbedder(model="nomic-embed-text", url=OLLAMA_URL)
    )
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
    hyde_prompt_template="Imagine a client/therapist asking about {text}. Simulate some dialogue",
    interventions=None,
):
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
        }
    )
    return results["window_retriever"]["context_windows"]


if False:
    import pprint

    pprint.pprint(rag_examples("a therapist explaining imagery", window_size=1, top_k=1))
    # this really requires a GPU or a Mac M1+
    pprint.pprint(hyde_examples("a therapist explaining imagery", window_size=1, top_k=1))
