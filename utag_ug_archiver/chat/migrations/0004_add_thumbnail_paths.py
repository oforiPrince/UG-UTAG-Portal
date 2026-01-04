from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0003_messageattachment_groupmessageattachment"),
    ]

# NOTE: This migration was duplicated by `0005_add_thumbnail_paths.py` in some
# branches which caused SQLite "duplicate column name" errors when both
# migrations were applied in different orders. The schema already includes
# `thumbnail_path` (added by `0005`), so keep this migration as a no-op to
# preserve historical migration numbering while avoiding re-running the same
# AddField operations.
    operations = [
        # Intentionally left empty; column existence is handled by the
        # companion migration 0005_add_thumbnail_paths.py. If you need to
        # remove this in the future, coordinate across environments so all
        # deployments have applied the migration.
    ]
