from pgvector.django import VectorExtension


from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0027_adderrorlog"),
    ]

    operations = [VectorExtension()]
