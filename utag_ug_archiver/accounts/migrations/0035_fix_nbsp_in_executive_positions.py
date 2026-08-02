# Data migration to fix non-breaking spaces in executive_position values

from django.db import migrations


def fix_nbsp_in_positions(apps, schema_editor):
    """Replace non-breaking spaces with regular spaces in executive_position."""
    User = apps.get_model('accounts', 'User')
    for user in User.objects.filter(executive_position__isnull=False):
        cleaned = user.executive_position.replace('\xa0', ' ')
        if cleaned != user.executive_position:
            user.executive_position = cleaned
            user.save(update_fields=['executive_position'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0034_alter_user_executive_position"),
    ]

    operations = [
        migrations.RunPython(fix_nbsp_in_positions, noop),
    ]
