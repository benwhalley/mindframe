import django.db.models.deletion
from django.db import migrations

from mindframe.shortuuidfield import MFShortUUIDField


def populate_shortuuid(apps, schema_editor):
    Conversation = apps.get_model("mindframe", "Conversation")
    from mindframe.settings import mfuuid

    for convo in Conversation.objects.all():
        convo.uuid = mfuuid()
        convo.save()


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0020_conversation_uuid"),
    ]

    operations = [
        migrations.RunPython(populate_shortuuid),
        migrations.AlterField(
            model_name="conversation",
            name="uuid",
            field=MFShortUUIDField(blank=False, editable=False, max_length=27, unique=True),
        ),
    ]
