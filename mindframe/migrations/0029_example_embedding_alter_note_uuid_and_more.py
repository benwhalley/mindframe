# Generated by Django 5.1.3 on 2024-11-12 14:54

import mindframe.models
import pgvector.django.indexes
import pgvector.django.vector
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0028_auto_20241112_1447"),
    ]

    operations = [
        migrations.AddField(
            model_name="example",
            name="embedding",
            field=pgvector.django.vector.VectorField(dimensions=384, null=True),
        ),
        migrations.AddIndex(
            model_name="example",
            index=pgvector.django.indexes.HnswIndex(
                ef_construction=64,
                fields=["embedding"],
                m=16,
                name="example_embedding_index",
                opclasses=["vector_l2_ops"],
            ),
        ),
    ]
