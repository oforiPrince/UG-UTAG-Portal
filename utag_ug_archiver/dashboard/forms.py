from django import forms
from dashboard.models import CarouselSlide


class CarouselSlideForm(forms.ModelForm):
    class Meta:
        model = CarouselSlide
        fields = ['title', 'description', 'image', 'order', 'is_published']