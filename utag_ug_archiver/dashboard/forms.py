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