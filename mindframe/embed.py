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
