# Generated migration for updating executive position names to abbreviated forms
# This migration converts old position names to new abbreviated names for consistency

from django.db import migrations

def migrate_position_names(apps, schema_editor):
    """
    Migrate old position names to new abbreviated names.
    """
    User = apps.get_model('accounts', 'User')
    
    # Mapping of old names to new names
    position_mapping = {
        'College of Humanities Rep': 'COH Rep',
        'College of Health Rep': 'CHS Rep',
        'College of Education Rep': 'COE Rep',
        'Past President': None,  # Remove Past President as it's no longer in the order
    }
    
    for old_name, new_name in position_mapping.items():
        if new_name is None:
            # For Past President, keep it as is (it's still in choices for backward compat)
            # but you could also remove it if desired
            continue
        
        User.objects.filter(executive_position=old_name).update(
            executive_position=new_name
        )

def reverse_migration(apps, schema_editor):
    """
    Reverse migration (convert back to old names).
    This is here for safety but typically won't be used.
    """
    User = apps.get_model('accounts', 'User')
    
    position_mapping_reverse = {
        'COH Rep': 'College of Humanities Rep',
        'CHS Rep': 'College of Health Rep',
        'COE Rep': 'College of Education Rep',
    }
    
    for new_name, old_name in position_mapping_reverse.items():
        User.objects.filter(executive_position=new_name).update(
            executive_position=old_name
        )

class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0031_alter_user_executive_position"),
    ]

    operations = [
        migrations.RunPython(migrate_position_names, reverse_migration),
    ]
