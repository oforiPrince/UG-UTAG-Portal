# Correct rename of User.rank -> User.academic_rank with safe DB handling
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0025_user_must_change_password'),
    ]

    operations = [
        migrations.RunSQL(
            sql=r'''
DO $$
BEGIN
    -- If both columns exist, keep academic_rank and drop rank after copying data
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'accounts_user' AND column_name = 'academic_rank'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'accounts_user' AND column_name = 'rank'
        ) THEN
            EXECUTE 'UPDATE accounts_user SET academic_rank = COALESCE(academic_rank, rank)';
            EXECUTE 'ALTER TABLE accounts_user DROP COLUMN rank';
        END IF;
    -- Else if only rank exists, rename it to academic_rank
    ELSIF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'accounts_user' AND column_name = 'rank'
    ) THEN
        EXECUTE 'ALTER TABLE accounts_user RENAME COLUMN rank TO academic_rank';
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
        END IF;
    END IF;
END$$;
'''
        ),
    ]
