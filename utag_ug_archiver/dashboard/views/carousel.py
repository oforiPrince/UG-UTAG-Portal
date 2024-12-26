from django.shortcuts import render
from django.views import View
from dashboard.models import Announcement, CarouselSlide, Notification
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from dashboard.forms import CarouselSlideForm


class CarouselSlideListView(View):
    template_name = 'dashboard_pages/carousel_slides.html'

    def get(self, request):
        slides = CarouselSlide.objects.all()
        
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()

        context = {
            'carousel_slides': slides,
            'notification_count': notification_count,
            'notifications': notifications
        }
        return render(request, self.template_name, context)
    

class CarouselSlideCreateUpdateView(View):
    template_name = 'dashboard_pages/forms/create_update_carousel.html'

    def get(self, request, slide_id=None):
        # Initialize variables
        new_announcements = []
        announcement_count = 0
        
        # Determine the user's role and fetch relevant data
        if request.user.groups.filter(name='Admin').exists():
            new_announcements = Announcement.objects.filter(status='PUBLISHED').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').count()
        elif request.user.has_perm('view_announcement'):
            if request.user.groups.filter(name='Executive').exists():
                announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Members').count()
                new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Members').order_by('-created_at')[:3]
            elif request.user.groups.filter(name='Member').exists():
                announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Executives').count()
                new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Executives').order_by('-created_at')[:3]

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
        else:
            messages.info(request, 'An error occurred while saving the carousel slide. Please try again.') 
            return render(request, self.template_name, {'form': form, 'carousel_slide': slide if slide_id else None})
    
class CarouselSlideDeleteView(View):
    def get(self, request, slide_id):
        slide = get_object_or_404(CarouselSlide, id=slide_id)
        slide.delete()
        return redirect('dashboard:carousel_slide_list')