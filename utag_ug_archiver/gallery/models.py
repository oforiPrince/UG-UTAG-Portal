from django.db import models
from django.db.models import Max
from django.core.files.storage import default_storage
from django.conf import settings
import os

def gallery_image_upload_to(instance, filename):
    """Generate upload path for gallery images."""
    gallery_id = instance.gallery.id if instance.gallery else 'general'
    return f'gallery_images/{gallery_id}/{filename}'

def gallery_thumbnail_upload_to(instance, filename):
    """Generate upload path for gallery thumbnails."""
    gallery_id = instance.gallery.id if instance.gallery else 'general'
    name, ext = os.path.splitext(filename)
    return f'gallery_images/{gallery_id}/thumbnails/{name}_thumb{ext}'

class Gallery(models.Model):
    title = models.CharField(max_length=255, help_text="Title of the gallery")
    description = models.TextField(blank=True, null=True, help_text="Optional description of the gallery")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date and time the gallery was created")
    is_active = models.BooleanField(default=True, help_text="Indicates whether the gallery is active")

    class Meta:
        verbose_name_plural = "Galleries"
        ordering = ['-created_at']

    def __str__(self):
        return self.title
    
    def get_image_count(self):
        """Return the number of images in this gallery."""
        return self.images.count()
    
    def get_cover_image(self):
        """Return the first image as cover, or None."""
        return self.images.first()

class Image(models.Model):
    gallery = models.ForeignKey(Gallery, related_name='images', on_delete=models.CASCADE, help_text="Gallery this image belongs to")
    image = models.ImageField(upload_to=gallery_image_upload_to, help_text="Upload image file")
    thumbnail = models.ImageField(upload_to=gallery_thumbnail_upload_to, blank=True, null=True, help_text="Auto-generated thumbnail")
    caption = models.CharField(max_length=255, blank=True, null=True, help_text="Optional caption for the image")
    uploaded_at = models.DateTimeField(auto_now_add=True, help_text="Date and time the image was uploaded")
    order = models.PositiveIntegerField(default=0, help_text="Display order within gallery")

    class Meta:
        ordering = ['order', '-uploaded_at']

    def __str__(self):
        return f"Image in {self.gallery.title} - {self.caption if self.caption else 'No Caption'}"
    
    def get_absolute_url(self):
        """Return the full-size image URL."""
        return self.image.url if self.image else ''
    
    def get_thumbnail_url(self):
        """Return thumbnail URL, or full image URL if thumbnail doesn't exist."""
        if self.thumbnail:
            return self.thumbnail.url
        return self.get_absolute_url()
    
    def save(self, *args, **kwargs):
        """Override save to generate thumbnail and optimize image."""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new and self.image:
            try:
                self._generate_thumbnail()
                self._optimize_image()
            except Exception as e:
                # Log error but don't fail the save
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to process image {self.id}: {e}")
    
    def _generate_thumbnail(self):
        """Generate a thumbnail for the image."""
        try:
            from PIL import Image as PILImage, ImageOps
        except ImportError:
            return  # PIL not available
        
        if not self.image:
            return
        
        try:
            # Open the original image
            img = PILImage.open(self.image.path)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = PILImage.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Create thumbnail (max 400x400, maintaining aspect ratio)
            img.thumbnail((400, 400), PILImage.LANCZOS)
            
            # Save thumbnail
            from django.core.files.base import ContentFile
            from io import BytesIO
            
            thumb_io = BytesIO()
            img.save(thumb_io, format='JPEG', quality=85, optimize=True)
            thumb_io.seek(0)
            
            # Generate thumbnail filename
            name, ext = os.path.splitext(os.path.basename(self.image.name))
            thumb_filename = f'{name}_thumb.jpg'
            
            # Save thumbnail
            self.thumbnail.save(thumb_filename, ContentFile(thumb_io.read()), save=False)
            self.save(update_fields=['thumbnail'])
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Thumbnail generation failed for image {self.id}: {e}")
    
    def _optimize_image(self):
        """Optimize the main image (resize if too large, compress)."""
        try:
            from PIL import Image as PILImage, ImageOps
        except ImportError:
            return  # PIL not available
        
        if not self.image:
            return
        
        try:
            # Open the original image
            img = PILImage.open(self.image.path)
            original_size = img.size
            
            # Max dimensions for gallery images (1920x1920 for web)
            max_dimension = 1920
            
            # Resize if image is too large
            if max(original_size) > max_dimension:
                img.thumbnail((max_dimension, max_dimension), PILImage.LANCZOS)
                
                # Save optimized image
                from django.core.files.base import ContentFile
                from io import BytesIO
                
                opt_io = BytesIO()
                
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = PILImage.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                img.save(opt_io, format='JPEG', quality=85, optimize=True)
                opt_io.seek(0)
                
                # Save optimized image
                name, ext = os.path.splitext(os.path.basename(self.image.name))
                opt_filename = f'{name}_opt.jpg'
                self.image.save(opt_filename, ContentFile(opt_io.read()), save=False)
                self.save(update_fields=['image'])
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Image optimization failed for image {self.id}: {e}")
