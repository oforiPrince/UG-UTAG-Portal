from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0027_user_academic_rank"),
    ]

    operations = [
        migrations.RunSQL(
            sql=r'''
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'accounts_user' AND column_name = 'academic_rank'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'accounts_user' AND column_name = 'rank'
        ) THEN
            EXECUTE 'ALTER TABLE accounts_user RENAME COLUMN rank TO academic_rank';
        ELSE
            EXECUTE 'ALTER TABLE accounts_user ADD COLUMN academic_rank varchar(50)';
        END IF;
    END IF;
END$$;
''',
            reverse_sql=r'''
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'accounts_user' AND column_name = 'academic_rank'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'accounts_user' AND column_name = 'rank'
        ) THEN
            EXECUTE 'ALTER TABLE accounts_user RENAME COLUMN academic_rank TO rank';
        ELSE
            EXECUTE 'ALTER TABLE accounts_user DROP COLUMN academic_rank';
        END IF;
    END IF;
END$$;
''',
        ),
    ]
