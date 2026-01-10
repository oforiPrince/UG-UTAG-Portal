# Generated migration to expand character limits for name and rank fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0028_ensure_academic_rank_column'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='other_name',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='user',
            name='surname',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='user',
            name='academic_rank',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
