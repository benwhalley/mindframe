# Generated by Django 5.1.3 on 2024-11-12 16:48

import django.db.models.deletion
import shortuuid.main
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0031_alter_note_uuid_alter_treatmentsession_uuid_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cycle",
            name="client",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cycles",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="cycle",
            name="intervention",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="Cycles",
                to="mindframe.intervention",
            ),
        ),
        migrations.AlterField(
            model_name="errorlog",
            name="session_state",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="mindframe.treatmentsessionstate",
            ),
        ),
        migrations.AlterField(
            model_name="note",
            name="judgement",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notes",
                to="mindframe.judgement",
            ),
        ),
        migrations.AlterField(
            model_name="note",
            name="uuid",
            field=models.CharField(
                default=shortuuid.main.ShortUUID.uuid, editable=False, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="treatmentsession",
            name="uuid",
            field=models.CharField(
                default=shortuuid.main.ShortUUID.uuid, editable=False, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="turn",
            name="speaker",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AlterField(
            model_name="turn",
            name="uuid",
            field=models.CharField(
                default=shortuuid.main.ShortUUID.uuid, editable=False, unique=True
            ),
        ),
    ]