from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0029_expand_name_and_rank_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='executive_summary',
            field=models.CharField(max_length=300, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='executive_bio',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='linkedin_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='twitter_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='personal_website_url',
            field=models.URLField(blank=True, null=True),
        ),
    ]
