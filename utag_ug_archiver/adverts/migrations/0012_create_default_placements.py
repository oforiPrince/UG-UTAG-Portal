"""Create common default Placement rows used across the site.

This ensures the dashboard modal's placements multi-select has sensible defaults
so admins can assign adverts without manually creating placement records first.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    Placement = apps.get_model('adverts', 'Placement')
    defaults = [
        ('top', 'Top'),
        ('sidebar', 'Sidebar'),
        ('bottom', 'Bottom'),
        ('hero', 'Hero'),
        ('footer', 'Footer'),
    ]
    for key, name in defaults:
        Placement.objects.get_or_create(key=key, defaults={'name': name})


def reverse(apps, schema_editor):
    # Keep placements if reversing; do not delete automatically to avoid data loss.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('adverts', '0011_remove_advertisement_position'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
