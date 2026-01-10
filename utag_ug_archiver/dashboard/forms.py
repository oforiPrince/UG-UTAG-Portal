from django import forms
from dashboard.models import CarouselSlide
from django.db import models
from django.db.models import F


class CarouselSlideForm(forms.ModelForm):
    class Meta:
        model = CarouselSlide
        fields = ['title', 'description', 'image', 'order', 'is_published']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['order'].required = False
        
    def save(self, commit=True):
        instance = super().save(commit=False)

        if not instance.order:
            last_order = CarouselSlide.objects.aggregate(
                max_order=models.Max('order')
            )['max_order'] or 0
            instance.order = last_order + 1
        else:
            # Resolve conflicts
            conflicting_slides = CarouselSlide.objects.filter(order=instance.order).exclude(pk=instance.pk)
            if conflicting_slides.exists():
                # Increment the order for conflicting slides and all subsequent ones
                CarouselSlide.objects.filter(order__gte=instance.order).exclude(pk=instance.pk).update(order=F('order') + 1)

        if commit:
            instance.save()
        return instance

class ExecutiveBioForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'title', 'academic_rank', 'profile_pic',
            'executive_summary', 'executive_bio',
            'linkedin_url', 'twitter_url', 'personal_website_url',
        ]
        widgets = {
            'executive_summary': forms.TextInput(attrs={'placeholder': 'Short professional summary (max 300 chars)'}),
            'executive_bio': forms.Textarea(attrs={'rows': 8, 'placeholder': 'Full professional bio: roles, achievements, publications, leadership, vision.'}),
            'linkedin_url': forms.URLInput(attrs={'placeholder': 'https://www.linkedin.com/in/...'}),
            'twitter_url': forms.URLInput(attrs={'placeholder': 'https://x.com/handle'}),
            'personal_website_url': forms.URLInput(attrs={'placeholder': 'https://your-website.com'}),
        }