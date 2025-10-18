from django.http import JsonResponse
import random
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.db.models import Q
from django.utils import timezone
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
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
        # Advertisements for homepage showcase
        today = timezone.now().date()
        active_adverts = (
            Advertisement.objects.select_related('advertiser', 'plan')
            .filter(
                status='PUBLISHED',
                start_date__lte=today,
            )
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
        )

        # Prefer using placements relation (recommended). Fall back to legacy position field if needed.
        top_adverts_qs = active_adverts.filter(placements__key='top')
        sidebar_adverts_qs = active_adverts.filter(placements__key='sidebar')
        bottom_adverts_qs = active_adverts.filter(placements__key='bottom')

        # We rely on placements relation for advert placement filtering.

        top_adverts = top_adverts_qs.order_by('-priority', '-start_date', '-created_at').distinct()[:5]
        sidebar_adverts = sidebar_adverts_qs.order_by('-priority', '-start_date', '-created_at').distinct()[:6]
        bottom_adverts = bottom_adverts_qs.order_by('-priority', '-start_date', '-created_at').distinct()[:4]

        context = {
            'published_events': published_events,
            'published_news': published_news,
            'executives': executives,
            'top_adverts': top_adverts,
            'sidebar_adverts': sidebar_adverts,
            'bottom_adverts': bottom_adverts,
            'large_advert_images': top_adverts,
            'small_advert_images': sidebar_adverts,
            'carousel_slides': carousel_slides,
            'gallery_images': gallery_images,
        }
        return render(request, self.template_name, context)
    
class AdClickRedirect(View):
    """Redirect endpoint that increments clicks then redirects to the advert target."""
    def get(self, request, pk):
        advert = Advertisement.objects.filter(pk=pk).first()
        if not advert:
            return JsonResponse({'error': 'Advert not found'}, status=404)
        advert.clicked()
        # If target is set, redirect; otherwise return JSON
        if advert.target_url:
            from django.shortcuts import redirect
            return redirect(advert.target_url)
        return JsonResponse({'message': 'click recorded'})

class AdImpressionPing(View):
    """Endpoint to be called via client-side JS when an advert is visible to increment impression count."""
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, pk):
        advert = Advertisement.objects.filter(pk=pk).first()
        if not advert:
            return JsonResponse({'error': 'Advert not found'}, status=404)

        # Determine requester identity for short-term debounce: prefer session_key, else IP
        session_key = getattr(request.session, 'session_key', None)
        if not session_key:
            # ensure session exists
            request.session.save()
            session_key = request.session.session_key

        requester_id = session_key or request.META.get('REMOTE_ADDR', 'anon')
        cache_key = f"ad_impression:{pk}:{requester_id}"

        # If we've recorded an impression for this requester recently, ignore
        if cache.get(cache_key):
            return JsonResponse({'message': 'already recorded recently'}, status=204)

        # Enforce cap
        if advert.impressions_cap is not None and advert.impressions_count >= advert.impressions_cap:
            return JsonResponse({'message': 'cap reached', 'impressions': advert.impressions_count}, status=403)

        # Record impression and set short debounce (60s)
        advert.increment_impression()
        cache.set(cache_key, 1, timeout=60)

        return JsonResponse({'message': 'impression recorded', 'impressions': advert.impressions_count})
    
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
