from django.shortcuts import render
from django.views import View
from dashboard.models import CarouselSlide
from django.shortcuts import get_object_or_404, redirect

from dashboard.forms import CarouselSlideForm


class CarouselSlideListView(View):
    template_name = 'dashboard_pages/carousel_slides.html'

    def get(self, request):
        slides = CarouselSlide.objects.all()
        context = {
            'carousel_slides': slides
        }
        return render(request, self.template_name, context)
    

class CarouselSlideCreateUpdateView(View):
    template_name = 'dashboard_pages/forms/create_update_carousel.html'

    def get(self, request, slide_id=None):
        if slide_id:
            slide = get_object_or_404(CarouselSlide, id=slide_id)
            form = CarouselSlideForm(instance=slide)
            initial_data = {
                'title': slide.title,
                'description': slide.description,
                'order': slide.order,
                'is_published': slide.is_published,
                'image': slide.image,
                'get_image_url': slide.image.url if slide.image else ''
            }
        else:
            form = CarouselSlideForm()
            initial_data = {}
        return render(request, self.template_name, {'form': form, 'initial_data': initial_data, 'carousel_slide': slide if slide_id else None})

    def post(self, request, slide_id=None):
        if slide_id:
            slide = get_object_or_404(CarouselSlide, id=slide_id)
            form = CarouselSlideForm(request.POST, request.FILES, instance=slide)
        else:
            form = CarouselSlideForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()
            return redirect('dashboard:carousel_slide_list')

        return render(request, self.template_name, {'form': form})
    
class CarouselSlideDeleteView(View):
    def post(self, request, slide_id):
        slide = get_object_or_404(CarouselSlide, id=slide_id)
        slide.delete()
        return redirect('dashboard:carousel_slide_list')