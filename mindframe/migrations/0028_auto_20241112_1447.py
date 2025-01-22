from pgvector.django import VectorExtension


from django.db import migrations


def f_():
    # wrap VectorExtension because it fails if not superuser (we may want to install the extension prior to running the migration if in production)
    try:
        return VectorExtension()
    except Exception as e:
        print(e)
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0027_adderrorlog"),
    ]

    operations = [f_()]
