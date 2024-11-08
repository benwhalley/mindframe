from django.db import migrations
import shortuuid

shortuuid.set_alphabet("abcdefghijklmnopqrstuvwxyz")


def gen_uuid(apps, schema_editor):
    Note = apps.get_model("mindframe", "Note")
    Turn = apps.get_model("mindframe", "Turn")
    for row in Note.objects.all():
        row.uuid = shortuuid.uuid()
        row.save(update_fields=["uuid"])
    for row in Turn.objects.all():
        row.uuid = shortuuid.uuid()
        row.save(update_fields=["uuid"])


class Migration(migrations.Migration):
    dependencies = [
        ("mindframe", "0020_note_uuid_turn_uuid_alter_example_unique_together"),
    ]

    operations = [
        migrations.RunPython(gen_uuid, reverse_code=migrations.RunPython.noop),
    ]
