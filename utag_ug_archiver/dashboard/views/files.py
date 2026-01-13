from django.contrib.auth.hashers import make_password
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse, Http404
from django.contrib.auth.models import Group
from django.db.models import Q
from django.core.cache import cache
import os

# use requests if available for quick HEAD checks, otherwise fall back to urllib
try:
    import requests
except Exception:
    requests = None
from dashboard.models import Announcement, Document, File, Notification

from utag_ug_archiver.utils.decorators import MustLogin

#For File Management
class DocumentsView(View):
    template_name = 'dashboard_pages/documents.html'

    @method_decorator(MustLogin)
    def get(self, request):
        # Get documents based on user role/group and public visibility
        documents = self.get_documents(request.user)
        
        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        
        context = {
            'documents': documents,
            'notifications': notifications,
            'notification_count': notification_count,
            'has_add_permission': request.user.has_perm('dashboard.add_document') or request.user.executive_position=="Secretary",
            'has_change_permission': request.user.has_perm('dashboard.change_document') or request.user.executive_position=="Secretary",
            'has_delete_permission': request.user.has_perm('dashboard.delete_document') or request.user.executive_position=="Secretary",
        }
        # Ensure each File has an absolute URL attribute for previewers
        PREVIEW_CACHE_TTL = 60 * 60  # 1 hour
        PREVIEWABLE_EXTS = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx'}

        def check_url_previewable(url, file_id):
            """Check whether a given absolute file URL appears publicly previewable.

            Uses a cached result (1 hour TTL) and performs a HEAD request with a
            very short timeout to avoid slowing page renders. Falls back to
            urllib if requests isn't available.
            """
            cache_key = f"file_previewable:{file_id}"
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

            # Quick safety checks
            if not url or not url.lower().startswith(('http://', 'https://')):
                cache.set(cache_key, False, PREVIEW_CACHE_TTL)
                return False

            try:
                if requests is not None:
                    # perform a light HEAD request with short timeout
                    r = requests.head(url, allow_redirects=True, timeout=2)
                    ok = (r.status_code >= 200 and r.status_code < 400)
                else:
                    # fallback to urllib
                    from urllib.request import Request, urlopen
                    req = Request(url, method='HEAD')
                    resp = urlopen(req, timeout=2)
                    ok = (200 <= resp.getcode() < 400)
            except Exception:
                ok = False

            cache.set(cache_key, ok, PREVIEW_CACHE_TTL)
            return ok

        for doc in documents:
            # documents could be a queryset; iterate files for each document
            for f in getattr(doc, 'files').all():
                try:
                    f.absolute_url = request.build_absolute_uri(f.file.url)
                except Exception:
                    # If file URL is invalid for any reason, set to relative URL
                    f.absolute_url = f.file.url if hasattr(f, 'file') else ''

                # Only attempt preview checks for known previewable extensions
                try:
                    _, ext = os.path.splitext(getattr(f, 'file').name)
                    ext = (ext or '').lower()
                except Exception:
                    ext = ''

                if ext in PREVIEWABLE_EXTS:
                    # check and attach boolean flag used by template
                    f.previewable = check_url_previewable(f.absolute_url, f.id)
                else:
                    f.previewable = False

        # Explicitly pass request into context to guarantee availability in templates
        context['request'] = request
        return render(request, self.template_name, context)

    def get_documents(self, user):
        # get user's group names
        group_names = user.groups.values_list('name', flat=True)
        if user.is_superuser:
            return Document.objects.all()
        elif user.groups.filter(name__in=['Executive', 'Member']).exists():
            return Document.objects.filter(visibility='selected_groups', visible_to_groups__in=user.groups.all())
        else:
            return Document.objects.filter(visibility='everyone')
    
    
class DeleteFileView(View):
    def post(self, request):
        file_id = request.POST.get('file_id')
        try:
            file_to_delete = File.objects.get(pk=file_id)
            file_to_delete.delete()
            return JsonResponse({'success': True})
        except File.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'File not found'})
        
class DeleteDocumentView(View):
    def get(self, request, document_id):
        document = Document.objects.get(pk=document_id)
        document.delete()
        messages.success(request, 'Document deleted successfully')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))  
    
class DocumentCreateUpdateView(View):
    template_name = 'dashboard_pages/forms/create_update_document.html'

    def get(self, request, document_id=None):
        if document_id:
            document = get_object_or_404(Document, pk=document_id)
        else:
            document = None

        from django.conf import settings
        context = {
            'document': document,
            'CATEGORY_CHOICES': Document.CATEGORY_CHOICES,
            'DOCUMENT_STATUS_CHOICES': Document.DOCUMENT_STATUS_CHOICES,
            'VISIBILITY_CHOICES': Document.VISIBILITY_CHOICES,
            'all_groups': Group.objects.all(),
            'tinymce_api_key': getattr(settings, 'TINYMCE_API_KEY', ''),
            'active_menu': 'documents'
        }
        return render(request, self.template_name, context)

    def post(self, request, document_id=None):
        if document_id:
            document = get_object_or_404(Document, pk=document_id)
            success_message = "Document has been updated successfully"
        else:
            document = Document()
            success_message = "Document has been created successfully"

        document.title = request.POST.get('title')
        document.sender = request.POST.get('sender')
        document.receiver = request.POST.get('receiver')
        document.category = request.POST.get('category')
        document.date = request.POST.get('date')
        document.description = request.POST.get('description')
        document.status = request.POST.get('status')
        document.visibility = request.POST.get('visibility')
        document.uploaded_by = request.user

        if document_id:
            document.save()  # Save the document to update it
        document.save()
        # Handle file uploads
        files = request.FILES.getlist('files')
        if files:
            for file in files:
                new_file = File(file=file)
                new_file.save()
                document.files.add(new_file)

        # Handle visibility and groups
        if document.visibility == 'selected_groups':
            visible_to_groups_ids = request.POST.getlist('visible_to_groups')
            document.visible_to_groups.set(visible_to_groups_ids)
        else:
            document.visible_to_groups.clear()

        document.save()
        messages.success(request, success_message)
        return redirect('dashboard:documents')