"""Seed default AdSlot records for 'top' and 'bottom' placements.

This data migration will ensure the two commonly-used placements exist
and have sensible recommended dimensions. It's safe to run multiple
times (idempotent) and will update sizes if they differ.
"""
from django.db import migrations


DEFAULT_SLOTS = {
    'top': {'name': 'Top', 'width': 1200, 'height': 600},
    'bottom': {'name': 'Bottom', 'width': 900, 'height': 300},
}


def create_or_update_slots(apps, schema_editor):
    AdSlot = apps.get_model('adverts', 'AdSlot')

    for key, info in DEFAULT_SLOTS.items():
        slot, created = AdSlot.objects.get_or_create(
            key=key,
            defaults={
                'name': info['name'],
                'width': info['width'],
                'height': info['height'],
            }
        )

        # If it already existed, ensure width/height and name are set to defaults
        changed = False
        if slot.name != info['name']:
            slot.name = info['name']
            changed = True
        if (not slot.width) or slot.width != info['width']:
            slot.width = info['width']
            changed = True
        if (not slot.height) or slot.height != info['height']:
            slot.height = info['height']
            changed = True

        if changed:
            slot.save(update_fields=['name', 'width', 'height'])


def noop_reverse(apps, schema_editor):
    # Intentionally do nothing on reverse to avoid accidental data loss.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('adverts', '0015_ad_created_by_advertplan_created_by_advertorder'),
    ]

    operations = [
        migrations.RunPython(create_or_update_slots, noop_reverse),
    ]
