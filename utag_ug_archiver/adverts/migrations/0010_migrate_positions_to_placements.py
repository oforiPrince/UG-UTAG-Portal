"""Data migration: convert legacy Advertisement.position values into Placement relations.

This creates Placement rows (slugified key) for any advert that has a non-empty
`position` and attaches the placement to the advert via the M2M. The reverse
operation is intentionally a no-op.
"""
from django.db import migrations
from django.utils.text import slugify


def forwards(apps, schema_editor):
    Placement = apps.get_model('adverts', 'Placement')
    Advertisement = apps.get_model('adverts', 'Advertisement')

    for ad in Advertisement.objects.all():
        pos = getattr(ad, 'position', None)
        if not pos:
            continue
        key = slugify(str(pos).strip())
        if not key:
            continue
        placement, _ = Placement.objects.get_or_create(key=key, defaults={'name': pos})
        # Attach placement to advert
        try:
            ad.placements.add(placement)
        except Exception:
            # If something goes wrong with the M2M for a particular row, skip it
            continue


def reverse(apps, schema_editor):
    # No-op reverse; don't remove placements automatically
    return


class Migration(migrations.Migration):

    dependencies = [
        ('adverts', '0009_placement_remove_advertplan_positions_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
