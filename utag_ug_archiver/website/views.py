from datetime import date
from django.shortcuts import render
from django.views import View
from dashboard.models import Event, News, Executive
from adverts.models import Advertisement
from utag_ug_archiver.utils.functions import officers_custom_order, members_custom_order
from utag_ug_archiver.utils.constants import officers_position_order, committee_members_position_order

class IndexView(View):
    template_name = 'website_pages/index.html'
    
    def get(self, request):
        published_events = Event.objects.filter(is_published=True).order_by('-date')[:5]
        published_news = News.objects.filter(is_published=True).order_by('-created_at')[:5]

        # Get all executives
        executives = Executive.objects.filter(position__name__in=officers_position_order, is_executive_officer=True)

        # Sort the executives based on the custom order
        executives = sorted(executives, key=officers_custom_order)
        
        # Advertisement
        active_ads = Advertisement.objects.filter(start_date__lte=date.today(), end_date__gte=date.today())
        print(active_ads)
        context = {
            'published_events': published_events,
            'published_news': published_news,
            'executives': executives,
            'active_ads': active_ads,
        }
        return render(request, self.template_name, context)
    
class AboutView(View):
    template_name = 'website_pages/about.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
class ContactView(View):
    template_name = 'website_pages/contact.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
class EventsView(View):
    template_name = 'website_pages/events.html'
    
    def get(self, request):
        all_events = Event.objects.filter(is_published=True).order_by('-created_at')
        
        context = {
            'all_events': all_events,
        }
        return render(request, self.template_name, context)
    
class EventsDetailView(View):
    template_name = 'website_pages/events_detail.html'
    
    def get(self, request, pk):
        event = Event.objects.get(pk=pk)
        context = {
            'event': event,
        }
        return render(request, self.template_name, context)
    
class NewsView(View):
    template_name = 'website_pages/news.html'
    
    def get(self, request):
        all_news = News.objects.filter(is_published=True).order_by('-created_at')
        
        context = {
            'all_news': all_news,
        }
        return render(request, self.template_name, context)
    
class NewsDetailView(View):
    template_name = 'website_pages/news_detail.html'
    
    def get(self, request, *args, **kwargs):
        news_id = kwargs.get('news_id')
        news = News.objects.get(id=news_id)
        context = {
            'news' : news
        }
        return render(request, self.template_name,context)
    
class ExecutiveOfficersView(View):
    template_name = 'website_pages/executive_officers.html'
    
    def get(self, request):
        # Get all executives
        executives = Executive.objects.filter(position__name__in=officers_position_order, is_executive_officer=True, is_active=True)

        # Sort the executives based on the custom order
        executives = sorted(executives, key=officers_custom_order)
        context = {
            'executives': executives,
        }
        return render(request, self.template_name, context)
        
class ExecutiveCommitteeMembersView(View):
    template_name = 'website_pages/executive_committee_members.html'
    
    def get(self, request):
        # Get all executives and include the committee members
        executives = Executive.objects.filter(position__name__in=officers_position_order+committee_members_position_order, is_active=True)
        # Sort the executives based on the custom order
        executives = sorted(executives, key=members_custom_order)
        context = {
            'executives': executives,
        }
        return render(request, self.template_name, context)