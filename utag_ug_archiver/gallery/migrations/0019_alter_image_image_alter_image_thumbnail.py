# Generated manually to align upload_to with callable paths
from django.db import migrations, models
import gallery.models


class Migration(migrations.Migration):

    dependencies = [
        ('gallery', '0018_image_thumbnail_image_order'),
    ]

    operations = [
        migrations.AlterField(
            model_name='image',
            name='image',
            field=models.ImageField(help_text='Upload image file', upload_to=gallery.models.gallery_image_upload_to),
        ),
        migrations.AlterField(
            model_name='image',
            name='thumbnail',
            field=models.ImageField(blank=True, help_text='Auto-generated thumbnail', null=True, upload_to=gallery.models.gallery_thumbnail_upload_to),
        ),
    ]