# Generated manually on 2026-02-02 14:30
"""
Data migration to populate access_token for existing ChatThread and ChatGroup records.
This ensures all existing chats have tokens for the new token-based URL security system.
"""
from django.db import migrations
import secrets


def generate_tokens_for_existing_chats(apps, schema_editor):
    """
    Generate access_token for all ChatThread and ChatGroup records that don't have one.
    This is needed for records created before the token fields were added.
    """
    ChatThread = apps.get_model('chat', 'ChatThread')
    ChatGroup = apps.get_model('chat', 'ChatGroup')
    
    # Update threads
    threads_updated = 0
    for thread in ChatThread.objects.filter(access_token__isnull=True):
        thread.access_token = secrets.token_urlsafe(48)
        thread.save()
        threads_updated += 1
    
    # Update groups  
    groups_updated = 0
    for group in ChatGroup.objects.filter(access_token__isnull=True):
        # Generate access_token if missing
        if not group.access_token:
            group.access_token = secrets.token_urlsafe(48)
        # Generate invite_token if missing (should have been created in migration 0008)
        if not group.invite_token:
            group.invite_token = secrets.token_urlsafe(48)
        group.save()
        groups_updated += 1
    
    if threads_updated > 0 or groups_updated > 0:
        print(f"✅ Populated tokens for {threads_updated} threads and {groups_updated} groups")


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - set access_token to None for all records.
    This is safe because the token fields are nullable.
    """
    ChatThread = apps.get_model('chat', 'ChatThread')
    ChatGroup = apps.get_model('chat', 'ChatGroup')
    
    ChatThread.objects.all().update(access_token=None)
    ChatGroup.objects.all().update(access_token=None)


class Migration(migrations.Migration):
    """
    Data migration to populate access tokens for existing chat records.
    Run after schema migrations 0008, 0009, and 0010 have added the token fields.
    """

    dependencies = [
        ('chat', '0010_chatgroup_access_token'),
    ]

    operations = [
        migrations.RunPython(
            generate_tokens_for_existing_chats,
            reverse_migration,
        ),
    ]
