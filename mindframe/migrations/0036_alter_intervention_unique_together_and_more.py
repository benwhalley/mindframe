# Generated by Django 5.1.3 on 2024-11-18 09:20

import mindframe.models
import shortuuid.main
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0035_intervention_informaton_alter_customuser_role_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="intervention",
            name="version",
            field=models.CharField(editable=False, max_length=64, null=True),
        ),
        migrations.AlterUniqueTogether(
            name="intervention",
            unique_together={("title", "version")},
        ),
    ]
