# Generated by Django 5.1.5 on 2025-02-10 00:40

from django.db import migrations

import mindframe.shortuuidfield


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="note",
            name="uuid",
            field=mindframe.shortuuidfield.ShortUUIDField(
                blank=True, editable=False, max_length=22, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="turn",
            name="uuid",
            field=mindframe.shortuuidfield.ShortUUIDField(
                blank=True, editable=False, max_length=22, unique=True
            ),
        ),
    ]
