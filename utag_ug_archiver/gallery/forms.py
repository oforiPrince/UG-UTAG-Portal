from django import forms
from django.core.exceptions import ValidationError
from .models import Gallery, Image
import os

# Maximum file size: 10MB
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
# Allowed image formats
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']

class GalleryForm(forms.ModelForm):
    class Meta:
        model = Gallery
        fields = ['title', 'description', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ImageUploadForm(forms.ModelForm):
    class Meta:
        model = Image
        fields = ['image', 'caption']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'multiple': False
            }),
            'caption': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional caption for this image'
            }),
        }
    
    def clean_image(self):
        """Validate uploaded image."""
        image = self.cleaned_data.get('image')
        if not image:
            return image
        
        # Check file size
        if image.size > MAX_UPLOAD_SIZE:
            raise ValidationError(
                f'Image file too large. Maximum size is {MAX_UPLOAD_SIZE / (1024*1024):.1f}MB.'
            )
        
        # Check file extension
        ext = os.path.splitext(image.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                f'Invalid file type. Allowed formats: {", ".join(ALLOWED_EXTENSIONS)}'
            )
        
        # Validate it's actually an image
        try:
            from PIL import Image as PILImage
            img = PILImage.open(image)
            img.verify()
            image.seek(0)  # Reset file pointer
        except Exception:
            raise ValidationError('Invalid image file. Please upload a valid image.')
        
        return image
