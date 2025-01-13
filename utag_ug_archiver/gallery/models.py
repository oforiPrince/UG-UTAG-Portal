from django.db import models

class Gallery(models.Model):
    title = models.CharField(max_length=255, help_text="Title of the gallery")
    description = models.TextField(blank=True, null=True, help_text="Optional description of the gallery")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date and time the gallery was created")
    is_active = models.BooleanField(default=True, help_text="Indicates whether the gallery is active")

    def __str__(self):
        return self.title



class Image(models.Model):
    gallery = models.ForeignKey(Gallery, related_name='images', on_delete=models.CASCADE, help_text="Gallery this image belongs to")
    image = models.ImageField(upload_to='gallery_images/', help_text="Upload image file")
    caption = models.CharField(max_length=255, blank=True, null=True, help_text="Optional caption for the image")
    uploaded_at = models.DateTimeField(auto_now_add=True, help_text="Date and time the image was uploaded")

    def __str__(self):
        return f"Image in {self.gallery.title} - {self.caption if self.caption else 'No Caption'}"
    
    def get_absolute_url(self):
        return self.image.url
