# Generated by Django 5.1.3 on 2024-11-18 12:41
import shortuuid
from django.db import migrations


# functionto set unique slug on Judgement
def set_unique_slug(apps, schema_editor):
    Judgement = apps.get_model("mindframe", "Judgement")

    # Generate and set UUID fo
    for j in Judgement.objects.all():
        j.slug = shortuuid.ShortUUID().uuid()
        print(j.slug)
        j.save()


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0040_judgement_slug_alter_note_uuid_and_more"),
    ]
    operations = [
        migrations.RunPython(set_unique_slug, reverse_code=migrations.RunPython.noop),
    ]
