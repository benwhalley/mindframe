from django.db import migrations, models
import shortuuid


def populate_uuids(apps, schema_editor):
    TreatmentSession = apps.get_model("mindframe", "TreatmentSession")
    for session in TreatmentSession.objects.all():
        session.uuid = shortuuid.uuid().lower()
        session.save()


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0008_treatmentsession_uuid"),
    ]

    operations = [
        migrations.RunPython(populate_uuids, reverse_code=migrations.RunPython.noop)
    ]
