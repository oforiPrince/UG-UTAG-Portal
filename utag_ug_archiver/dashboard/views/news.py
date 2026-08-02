from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.contrib import messages
from django.http import HttpResponseRedirect



from dashboard.models import Announcement, AttachedDocument, Citation, News, Notification, Tag

from utag_ug_archiver.utils.decorators import MustLogin

class NewsView(View):
    template_name = 'dashboard_pages/news.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all news
        news = News.objects.all()
        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        
        context = {
            'newss' : news,
            'notifications' : notifications,
            'notification_count' : notification_count
        }
        return render(request, self.template_name, context)


class NewsCreateUpdateView(View):
    template_name = 'dashboard_pages/forms/create_update_news.html'

    @method_decorator(MustLogin)
    def get(self, request, news_id=None):
        tags = Tag.objects.all()
        news = None
        try:
            if news_id:
                news = get_object_or_404(News, id=news_id)
                # Prefill form including created_at for backdating support (use datetime, not formatted string)
                try:
                    created_at_val = timezone.localtime(news.created_at) if news.created_at else None
                    created_at_iso = created_at_val.strftime('%Y-%m-%dT%H:%M') if created_at_val else None
                except Exception:
                    created_at_val = None
                    created_at_iso = None

                initial_data = {
                    'title': news.title,
                    'content': news.content,
                    'is_published': news.is_published,
                    'featured_image': news.featured_image.url if news.featured_image else None,
                    'tags': [tag.id for tag in news.tags.all()],
                    'citations': news.citations.all(),
                    'attached_documents': news.attached_documents.all(),
                    'created_at': created_at_val,
                    'created_at_iso': created_at_iso,
                }
            else:
                # Default created_at to now for new news entries (timezone-aware datetime)
                try:
                    default_created_at = timezone.localtime(timezone.now())
                    default_created_at_iso = default_created_at.strftime('%Y-%m-%dT%H:%M') if default_created_at else None
                except Exception:
                    default_created_at = None
                    default_created_at_iso = None

                initial_data = {
                    'title': '',
                    'content': '',
                    'is_published': False,
                    'tags': [],
                    'citations': [],
                    'attached_documents': [],
                    'featured_image': None,
                    'created_at': default_created_at,
                    'created_at_iso': default_created_at_iso,
                }
            return render(request, self.template_name, {'initial_data': initial_data, 'news': news, 'tags': tags, 'active_menu': 'news'})
        except Exception as e:
            messages.error(request, f"Error loading news form: {e}")
            return redirect('dashboard:news')

    @method_decorator(MustLogin)
    def post(self, request, news_id=None):
        user = request.user
        title = request.POST.get('title')
        content = request.POST.get('content')
        is_published = request.POST.get('is_published') == 'on'
        featured_image = request.FILES.get('featured_image')
        created_at_raw = request.POST.get('created_at')
        created_at_dt = None
        if created_at_raw:
            try:
                dt = parse_datetime(created_at_raw)
                if dt is None:
                    # parse_datetime may return None for date-only or unsupported formats
                    # try a simple ISO parse fallback
                    dt = timezone.datetime.fromisoformat(created_at_raw)
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt, timezone.get_current_timezone())
                created_at_dt = dt
            except Exception:
                created_at_dt = None

        try:
            # Handle tags
            raw_tags = [tag.strip() for tag in request.POST.getlist('tags')]
            tags = []
            for tag_value in raw_tags:
                if not tag_value:
                    continue
                if tag_value.isdigit():
                    try:
                        tags.append(Tag.objects.get(pk=int(tag_value)))
                    except Tag.DoesNotExist:
                        continue
                else:
                    tag, _ = Tag.objects.get_or_create(name=tag_value)
                    tags.append(tag)

            if news_id:
                news = get_object_or_404(News, id=news_id)
                news.title = title
                news.content = content
                news.is_published = is_published
                if featured_image:
                    news.featured_image = featured_image
                # Allow backdating created_at if provided
                if created_at_dt:
                    news.created_at = created_at_dt
                news.save()
                # Update tags
                news.tags.clear()
                for tag in tags:
                    news.tags.add(tag)
                self._handle_citations(request, news)
                self._handle_documents(request, news)
                messages.success(request, "News updated successfully!")
            else:
                # Create with optional created_at override for backdating
                create_kwargs = dict(
                    author=user,
                    title=title,
                    content=content,
                    is_published=is_published,
                    featured_image=featured_image
                )
                if created_at_dt:
                    create_kwargs['created_at'] = created_at_dt
                news = News.objects.create(**create_kwargs)
                for tag in tags:
                    news.tags.add(tag)
                self._handle_citations(request, news)
                self._handle_documents(request, news)
                messages.success(request, "News created successfully!")

            return redirect('dashboard:news')

        except Exception as e:
            messages.error(request, f"Error saving news: {e}")
            return redirect('dashboard:news')

    def _handle_citations(self, request, news):
        """
        Handle adding/updating citations for a news item.
        """
        citation_sources = request.POST.getlist('citation_sources[]')
        citation_urls = request.POST.getlist('citation_urls[]')
        citation_descriptions = request.POST.getlist('citation_descriptions[]')

        # Clear existing citations
        news.citations.all().delete()

        for source, url, description in zip(citation_sources, citation_urls, citation_descriptions):
            if source and url:  # Ensure valid citations
                Citation.objects.create(
                    news=news,
                    source_name=source,
                    url=url,
                    description=description
                )

    def _handle_documents(self, request, news):
        """
        Handle adding/updating attached documents for a news item.
        """
        document_names = request.POST.getlist('document_names[]')
        document_files = request.FILES.getlist('document_files[]')

        existing_documents = {doc.name: doc for doc in news.attached_documents.all()}

        # Update existing or add new documents
        for name, file in zip(document_names, document_files):
            if name and file:  # Ensure valid documents
                if name in existing_documents:  # If the document already exists, update the file
                    existing_document = existing_documents[name]
                    existing_document.file = file
                    existing_document.save()
                else:  # Add new document
                    AttachedDocument.objects.create(
                        news=news,
                        name=name,
                        file=file
                    )

        # Remove documents whose names are not in the updated list
        for doc_name in existing_documents.keys():
            if doc_name not in document_names:
                existing_documents[doc_name].delete()


    
class NewsUpdateView(View):
    
    @method_decorator(MustLogin)
    def post(self, request, pk):
        user = request.user
        title = request.POST.get('title')
        content = request.POST.get('content')
        is_published = request.POST.get('is_published')
        featured_image = request.FILES.get('featured_image')
        created_at_raw = request.POST.get('created_at')
        if created_at_raw:
            try:
                dt = parse_datetime(created_at_raw)
                if dt is None:
                    dt = timezone.datetime.fromisoformat(created_at_raw)
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt, timezone.get_current_timezone())
                created_at_dt = dt
            except Exception:
                created_at_dt = None
        else:
            created_at_dt = None
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
        if created_at_dt:
            news.created_at = created_at_dt
        news.save()
        messages.info(request, "News Updated Successfully")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class NewsDetailView(View):
    template_name = 'dashboard_pages/news_detail.html'
    
    @method_decorator(MustLogin)
    def get(self, request, news_id):
        news = get_object_or_404(News, id=news_id)
        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        
        context = {
            'news': news,
            'notifications': notifications,
            'notification_count': notification_count,
            'active_menu': 'news'
        }
        return render(request, self.template_name, context)


class NewsDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        news_id = kwargs.get('news_id')
        news = News.objects.get(pk=news_id)
        news.delete()
        messages.info(request, "News Deleted Successfully")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
