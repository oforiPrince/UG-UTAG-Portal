from django import forms
from .models import Gallery, Image

class GalleryForm(forms.ModelForm):
    class Meta:
        model = Gallery
        fields = ['title', 'description', 'is_active']


class ImageUploadForm(forms.ModelForm):
    class Meta:
        model = Image
        fields = ['image', 'caption']  # Ensure 'image' is included
