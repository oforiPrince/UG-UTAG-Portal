from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("adverts", "0016_seed_top_bottom_adslots"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="ad",
            name="alt_text",
        ),
    ]
