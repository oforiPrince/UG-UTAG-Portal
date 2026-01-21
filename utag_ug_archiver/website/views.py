import random
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views import View
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from dashboard.models import CarouselSlide, Event, News
from accounts.models import User
from gallery.models import Gallery, Image
from utag_ug_archiver.utils.functions import executive_members_custom_order, executive_committee_members_custom_order
from utag_ug_archiver.utils.constants import executive_members_position_order, executive_committee_members_position_order
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

@method_decorator(cache_page(60 * 15), name='dispatch')  # Cache for 15 minutes
class IndexView(View):
    """
    Optimized homepage view with performance enhancements:
    - Uses select_related/only() to minimize database queries
    - Limits queryset results early to reduce memory usage
    - Only fetches required fields to reduce data transfer
    - Template conditionally renders sections only when data exists
    - Cached for 15 minutes to reduce database load
    """
    template_name = 'website_pages/index-v2.html'
    
    def get(self, request):
        # Optimize queries with select_related and prefetch_related
        # Only fetch what's needed, limit results early
        published_events = Event.objects.filter(
            is_published=True
        ).select_related(
            'created_by'
        ).only(
            'id', 'title', 'event_slug', 'description', 'start_date', 'end_date', 
            'venue', 'featured_image', 'created_at'
        ).order_by('-start_date')[:5]
        
        published_news = News.objects.filter(
            is_published=True
        ).select_related(
            'author'
        ).only(
            'id', 'title', 'news_slug', 'content', 'featured_image', 'created_at'
        ).order_by('-created_at')[:5]

        # Get executives with optimized query
        executives = User.objects.filter(
            executive_position__in=executive_members_position_order, 
            is_active_executive=True
        ).only(
            'id', 'other_name', 'surname', 'title', 'executive_position', 
            'executive_image', 'email', 'fb_profile_url', 
            'twitter_profile_url', 'linkedin_profile_url'
        )
        
        # Sort the executives based on the custom order
        executives = sorted(executives, key=executive_members_custom_order)
        
        # Get 4 gallery images for the homepage - optimized query
        gallery_images = []
        all_images = Image.objects.filter(
            gallery__is_active=True
        ).select_related('gallery').only(
            'id', 'image', 'caption', 'gallery__id', 'gallery__title'
        )
        
        image_count = all_images.count()
        if image_count >= 4:
            # Use random.sample for better performance than converting to list first
            gallery_images = random.sample(list(all_images), 4)
        
        carousel_slides = CarouselSlide.objects.filter(
            is_published=True
        ).only(
            'id', 'title', 'image', 'order', 'link_url'
        ).order_by('order')

        context = {
            'published_events': published_events,
            'published_news': published_news,
            'executives': executives,
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
        from django.db.models import Q
        # Get all executives and committee members: those with positions in the order list OR marked as active executives
        # Show all, including past executives (those whose term has ended)
        executives = User.objects.filter(
            Q(executive_position__in=executive_committee_members_position_order) | Q(is_active_executive=True)
        )
        # Sort the executives based on the custom order
        executives = sorted(
            executives, 
            key=lambda x: executive_committee_members_position_order.index(x.executive_position) 
                         if x.executive_position and x.executive_position in executive_committee_members_position_order 
                         else len(executive_committee_members_position_order)
        )
        context = {
            'executives': executives,
        }
        return render(request, self.template_name, context)

class ExecutivesListView(View):
    template_name = 'website_pages/executives_list.html'

    def get(self, request):
        executives = (
            User.objects.filter(is_active_executive=True)
            .select_related('school', 'college', 'department')
            .order_by('surname', 'other_name')
        )
        return render(request, self.template_name, {'executives': executives})


class ExecutiveDetailView(View):
    template_name = 'website_pages/executive_detail.html'

    def get(self, request, pk):
        exec_user = get_object_or_404(User.objects.select_related('school', 'college', 'department'), pk=pk)
        return render(request, self.template_name, {'exec': exec_user})
    
@method_decorator(cache_page(60 * 10), name='dispatch')  # Cache for 10 minutes
class GalleryView(View):
    template_name = 'website_pages/gallery-v2.html'

    def get(self, request):
        """
        Optimized gallery view with performance enhancements.
        Fetch only active galleries with optimized queries.
        """
        # Optimize queries - only fetch active galleries with images
        galleries = Gallery.objects.filter(
            is_active=True
        ).prefetch_related(
            'images'
        ).only(
            'id', 'title', 'description', 'created_at'
        ).order_by('-created_at')
        
        # Only include galleries that have at least one image
        galleries = [g for g in galleries if g.images.exists()]
            
        context = {
            'galleries': galleries,
        }
        return render(request, self.template_name, context)
        
    
class AddClick(View):
    pass
