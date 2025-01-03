# Generated by Django 5.1.3 on 2024-11-18 12:53

import shortuuid.main
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0041_auto_20241118_1241"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="judgement",
            unique_together={("intervention", "slug"), ("intervention", "title")},
        ),
        migrations.AlterUniqueTogether(
            name="transition",
            unique_together={("from_step", "to_step")},
        ),
    ]
