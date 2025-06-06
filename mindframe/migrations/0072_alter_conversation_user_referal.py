# Generated by Django 5.2 on 2025-06-01 09:12

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0071_auto_20250601_1003"),
    ]

    operations = [
        migrations.AlterField(
            model_name="conversation",
            name="user_referal",
            field=models.ForeignKey(
                default=1, on_delete=django.db.models.deletion.CASCADE, to="mindframe.userreferal"
            ),
            preserve_default=False,
        ),
    ]
