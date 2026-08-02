# Generated manually on 2026-02-03 05:15
"""
Data migration to fix duplicate invite_token issue.
Generates unique invite tokens for all ChatGroup records that have duplicates,
then adds the unique constraint.
"""
from django.db import migrations
import secrets


def populate_unique_invite_tokens(apps, schema_editor):
    """
    Generate unique invite_token for all ChatGroup records.
    Replace the default duplicated token with unique ones.
    """
    ChatGroup = apps.get_model('chat', 'ChatGroup')
    
    groups_updated = 0
    # Get all groups and ensure each has a unique token
    for group in ChatGroup.objects.all():
        # Generate a new unique token for each group
        group.invite_token = secrets.token_urlsafe(48)
        group.save()
        groups_updated += 1
    
    if groups_updated > 0:
        print(f"✅ Generated unique invite_tokens for {groups_updated} groups")


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - set invite_token back to the default.
    """
    ChatGroup = apps.get_model('chat', 'ChatGroup')
    ChatGroup.objects.all().update(invite_token="dsfhdshfsfsdfsdf")


class Migration(migrations.Migration):
    """
    Data migration to fix duplicate invite_token issue.
    This must run after 0008 and before adding the unique constraint.
    """

    dependencies = [
        ('chat', '0011_populate_access_tokens'),
    ]

    operations = [
        migrations.RunPython(
            populate_unique_invite_tokens,
            reverse_migration,
        ),
    ]
