# Generated manually for gallery optimization
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gallery', '0002_gallery_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='image',
            name='thumbnail',
            field=models.ImageField(blank=True, null=True, upload_to='gallery_images/general/thumbnails/', help_text='Auto-generated thumbnail'),
        ),
        migrations.AddField(
            model_name='image',
            name='order',
            field=models.PositiveIntegerField(default=0, help_text='Display order within gallery'),
        ),
        migrations.AlterModelOptions(
            name='gallery',
            options={'ordering': ['-created_at'], 'verbose_name_plural': 'Galleries'},
        ),
        migrations.AlterModelOptions(
            name='image',
            options={'ordering': ['order', '-uploaded_at']},
        ),
    ]

