"""Image optimization utilities for UTAG-UG Portal."""

import os
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


class ImageOptimizer:
    """Optimize uploaded images for web performance."""
    
    # Maximum dimensions for different image types
    MAX_DIMENSIONS = {
        'profile': (800, 800),
        'executive': (800, 800),
        'event': (1200, 800),
        'news': (1200, 800),
        'gallery': (1920, 1080),
        'thumbnail': (400, 400),
    }
    
    # Quality settings
    JPEG_QUALITY = 85
    WEBP_QUALITY = 80
    PNG_OPTIMIZE = True
    
    @staticmethod
    def optimize_image(image_file, image_type='default', max_size_kb=500):
        """
        Optimize an image file for web delivery.
        
        Args:
            image_file: Django ImageField or file path
            image_type: Type of image (profile, event, news, etc.)
            max_size_kb: Maximum file size in KB
            
        Returns:
            Optimized image file
        """
        try:
            # Open image
            if hasattr(image_file, 'path'):
                img = Image.open(image_file.path)
            else:
                img = Image.open(image_file)
            
            # Get max dimensions for this image type
            max_width, max_height = ImageOptimizer.MAX_DIMENSIONS.get(
                image_type, (1200, 1200)
            )
            
            # Resize if necessary (maintain aspect ratio)
            if img.width > max_width or img.height > max_height:
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Convert RGBA to RGB for JPEG
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode in ('RGBA', 'LA'):
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save optimized image
            output = BytesIO()
            img.save(
                output,
                format='JPEG',
                quality=ImageOptimizer.JPEG_QUALITY,
                optimize=True,
                progressive=True
            )
            output.seek(0)
            
            # Check file size and reduce quality if needed
            if output.tell() > max_size_kb * 1024:
                output = ImageOptimizer._reduce_quality(img, max_size_kb)
            
            return ContentFile(output.read())
            
        except Exception as e:
            # Log error but don't fail
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Image optimization failed: {e}")
            return image_file
    
    @staticmethod
    def _reduce_quality(img, max_size_kb):
        """Iteratively reduce quality until file size is acceptable."""
        quality = ImageOptimizer.JPEG_QUALITY
        output = BytesIO()
        
        while quality > 50:
            output = BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            output.seek(0)
            
            if output.tell() <= max_size_kb * 1024:
                break
            
            quality -= 5
        
        output.seek(0)
        return output
    
    @staticmethod
    def create_thumbnail(image_file, size=(400, 400)):
        """
        Create a thumbnail from an image file.
        
        Args:
            image_file: Django ImageField or file path
            size: Tuple of (width, height) for thumbnail
            
        Returns:
            Thumbnail image file
        """
        try:
            # Open image
            if hasattr(image_file, 'path'):
                img = Image.open(image_file.path)
            else:
                img = Image.open(image_file)
            
            # Create thumbnail
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode in ('RGBA', 'LA'):
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save thumbnail
            output = BytesIO()
            img.save(
                output,
                format='JPEG',
                quality=ImageOptimizer.JPEG_QUALITY,
                optimize=True
            )
            output.seek(0)
            
            return ContentFile(output.read())
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Thumbnail creation failed: {e}")
            return None
    
    @staticmethod
    def get_optimized_url(image_field, thumbnail=False):
        """
        Get the URL for an image, with fallback to placeholder.
        
        Args:
            image_field: Django ImageField
            thumbnail: Whether to return thumbnail URL
            
        Returns:
            Image URL string
        """
        if not image_field:
            return '/static/dashboard/assets/images/users/profile.png'
        
        try:
            return image_field.url
        except (ValueError, AttributeError):
            return '/static/dashboard/assets/images/users/profile.png'
