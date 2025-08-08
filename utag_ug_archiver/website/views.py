from datetime import date
from django.http import JsonResponse
import random
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.db.models import Q
from dashboard.models import CarouselSlide, Event, News
from adverts.models import Advertisement
from accounts.models import User
from gallery.models import Gallery, Image
from utag_ug_archiver.utils.functions import executive_members_custom_order, executive_committee_members_custom_order
from utag_ug_archiver.utils.constants import executive_members_position_order, executive_committee_members_position_order
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

class IndexView(View):
    template_name = 'website_pages/index-v2.html'
    
    def get(self, request):
        published_events = Event.objects.filter(is_published=True).order_by('-start_date')[:5]
        published_news = News.objects.filter(is_published=True).order_by('-created_at')[:5]

        # Get all executives
        executives = User.objects.filter(executive_position__in=executive_members_position_order, is_active_executive=True)
        
        # Get 4 gallery images for the homepage
        gallery_images = []
        
        # Method 1: Get 4 random images from all galleries
        all_images = Image.objects.filter(gallery__is_active=True).select_related('gallery')
        if all_images.count() >= 4:
            gallery_images = random.sample(list(all_images), 4)
        # Sort the executives based on the custom order
        executives = sorted(executives, key=executive_members_custom_order)
        carousel_slides = CarouselSlide.objects.filter(is_published=True).order_by('order')
        # Advertisement
        today = date.today()

        large_advertisements = []
        small_advertisements = []
        

        advertisements = Advertisement.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).order_by('created_at')
        for advert in advertisements:
            if advert.image_width == 900 and advert.image_height == 250:
                large_advertisements.append(advert)
            elif advert.image_width == 300 and advert.image_height == 250:
                small_advertisements.append(advert)

        context = {
            'published_events': published_events,
            'published_news': published_news,
            'executives': executives,
            'large_advert_images': large_advertisements,
            'small_advert_images': small_advertisements,
            'carousel_slides': carousel_slides,
            'gallery_images': gallery_images,
        }
        return render(request, self.template_name, context)
    
class AboutView(View):
    template_name = 'website_pages/about-v2.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
class ContactView(View):
    template_name = 'website_pages/contact-v2.html'
    
    def get(self, request):
        return render(request, self.template_name)
    

class EventsView(View):
    template_name = 'website_pages/events-v2.html'

    def get(self, request):
        event_list = Event.objects.filter(is_published=True).order_by('-created_at')
        page = request.GET.get('page', 1)
        paginator = Paginator(event_list, 12)
        try:
            events_page = paginator.page(page)
        except PageNotAnInteger:
            events_page = paginator.page(1)
        except EmptyPage:
            events_page = paginator.page(paginator.num_pages)

        context = {
            'events_page': events_page,
            'paginator': paginator,
        }
        print(f"Context: {context}")  # Debugging line to check context
        return render(request, self.template_name, context)

    
class NewsView(View):
    template_name = 'website_pages/news-v2.html'

    def get(self, request):
        news_list = News.objects.filter(is_published=True).order_by('-created_at')
        page = request.GET.get('page', 1)
        paginator = Paginator(news_list, 12)
        try:
            news_page = paginator.page(page)
        except PageNotAnInteger:
            news_page = paginator.page(1)
        except EmptyPage:
            news_page = paginator.page(paginator.num_pages)

        context = {
            'news_page': news_page,
            'paginator': paginator,
        }
        return render(request, self.template_name, context)

class NewsDetailView(View):
    template_name = 'website_pages/news_detail-v2.html'
    
    def get(self, request, *args, **kwargs):
        news_slug = kwargs.get('slug')
        news = get_object_or_404(News, news_slug=news_slug)
        latest_news = News.objects.filter(is_published=True).exclude(id=news.id).order_by('-created_at')[:3]
        context = {
            'news': news,
            'latest_news': latest_news
        }
        return render(request, self.template_name, context)


class EventsDetailView(View):
    template_name = 'website_pages/events_detail-v2.html'
    
    def get(self, request, *args, **kwargs):
        event_slug = kwargs.get('slug')
        event = get_object_or_404(Event, event_slug=event_slug)
        context = {
            'event': event,
        }
        return render(request, self.template_name, context)

    
class ExecutiveOfficersView(View):
    template_name = 'website_pages/executive_officers-v2.html'
    
    def get(self, request):
        # Get all executives
        executives = User.objects.filter(executive_position__in=executive_members_position_order, is_active_executive=True)

        # Sort the executives based on the custom order
        executives = sorted(executives, key=executive_members_custom_order)
        context = {
            'executives': executives,
        }
        return render(request, self.template_name, context)
        
class ExecutiveCommitteeMembersView(View):
    template_name = 'website_pages/executive_committee_members-v2.html'
    
    def get(self, request):
        # Get all executives and include the committee members
        executives = User.objects.filter(executive_position__in=executive_committee_members_position_order, is_active_executive=True)
        # Sort the executives based on the custom order
        executives = sorted(executives, key=executive_committee_members_custom_order)
        context = {
            'executives': executives,
        }
        return render(request, self.template_name, context)
    
class GalleryView(View):
    template_name = 'website_pages/gallery-v2.html'

    def get(self, request):
        """
        Handle GET requests to display the gallery with pagination.
        Fetch all active galleries and their associated images.
        """
        galleries = Gallery.objects.prefetch_related('images').order_by('-created_at')
            
        context = {
            'galleries': galleries,
        }
        return render(request, self.template_name, context)
        
    
class AddClick(View):
    def get(self, request, pk):
        advert = Advertisement.objects.get(pk=pk)
        advert.clicked()
        return JsonResponse({'message': 'success'})
