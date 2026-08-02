# Generated manually on 2026-02-03 05:16
"""
Schema migration to add unique constraint to ChatGroup.invite_token.
This runs after the data migration that populates unique tokens.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0012_populate_and_fix_invite_tokens'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chatgroup',
            name='invite_token',
            field=models.CharField(
                db_index=True,
                editable=False,
                max_length=64,
                unique=True,
                null=False,
            ),
        ),
    ]
