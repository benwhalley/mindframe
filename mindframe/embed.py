# this is a demo of how to use embedding to identify
# relevant examples based on a query
# we need to do a lot more work on how we expose RAG features to users
# through prompt templates

from mindframe.models import Example
from sentence_transformers import SentenceTransformer
from pgvector.django import L2Distance

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

egs = Example.objects.filter(embedding__isnull=True)
texts = list(egs.values_list("text", flat=True))
embeddings = model.encode(texts)
for eg, em in zip(egs, embeddings):
    eg.embedding = em
    eg.save()

q = model.encode("fat cat")
Example.objects.order_by(L2Distance("embedding", q))

q = model.encode("imagery")
Example.objects.order_by(L2Distance("embedding", q))
