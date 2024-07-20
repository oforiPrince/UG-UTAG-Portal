from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect



from dashboard.models import Announcement, News

from utag_ug_archiver.utils.decorators import MustLogin

class NewsView(View):
    template_name = 'dashboard_pages/news.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all news
        news = News.objects.all()
        if request.user.is_admin:
            new_announcements = Announcement.objects.filter(status='PUBLISHED').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').count()
        elif request.user.is_secretary or request.user.is_executive:
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Member').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Member').order_by('-created_at')[:3]
        elif request.user.is_member:
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Executive').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Executive').order_by('-created_at')[:3]
        context = {
            'newss' : news,
            'announcement_count' : announcement_count,
            'new_announcements' : new_announcements
        }
        return render(request, self.template_name, context)
    
class NewsCreateUpdateView(View):
    template_name = 'dashboard_pages/forms/create_update_news.html'

    @method_decorator(MustLogin)
    def get(self, request, news_id=None):
        if news_id:
            news = News.objects.get(id=news_id)
            initial_data = {
                'title': news.title,
                'content': news.content,
                'is_published': 'on' if news.is_published else 'off',
                'featured_image': news.featured_image
            }
        else:
            initial_data = {
                'is_published': 'off'
            }
        return render(request, self.template_name, {'initial_data': initial_data})

    @method_decorator(MustLogin)
    def post(self, request, news_id=None):
        user = request.user
        title = request.POST.get('title')
        content = request.POST.get('content')
        is_published = request.POST.get('is_published')
        featured_image = request.FILES.get('featured_image')

        if is_published == 'on':
            is_published = True
        else:
            is_published = False

        if news_id:
            news = News.objects.get(id=news_id)
            news.title = title
            news.content = content
            news.is_published = is_published
            news.featured_image = featured_image
            news.save()
            messages.info(request, "News Updated Successfully")
        else:
            news = News.objects.create(
                author=user,
                title=title,
                content=content,
                is_published=is_published,
                featured_image=featured_image
            )
            news.save()
            messages.info(request, "News Created Successfully")

        return redirect('dashboard:news')

    
class NewsUpdateView(View):
    
    @method_decorator(MustLogin)
    def post(self, request, pk):
        user = request.user
        title = request.POST.get('title')
        content = request.POST.get('content')
        is_published = request.POST.get('is_published')
        featured_image = request.FILES.get('featured_image')
        if is_published == 'on':
            is_published = True
        else:
            is_published = False
        news = News.objects.get(pk=pk)
        news.author = user
        news.title = title
        news.content = content
        news.is_published = is_published
        if featured_image:
            news.featured_image = featured_image
        news.save()
        messages.info(request, "News Updated Successfully")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class NewsDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        news_id = kwargs.get('news_id')
        news = News.objects.get(pk=news_id)
        news.delete()
        messages.info(request, "News Deleted Successfully")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
