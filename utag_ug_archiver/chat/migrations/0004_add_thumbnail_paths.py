from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0003_messageattachment_groupmessageattachment"),
    ]

    operations = [
        migrations.AddField(
            model_name='messageattachment',
            name='thumbnail_path',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='groupmessageattachment',
            name='thumbnail_path',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
