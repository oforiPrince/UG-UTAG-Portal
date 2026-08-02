from django.shortcuts import get_object_or_404, render
from django.views import View
from django.utils.decorators import method_decorator
from django.http import Http404

from dashboard.models import Document, Notification
from utag_ug_archiver.utils.decorators import MustLogin


class DocumentDetailView(View):
    """Standalone page view for document details"""
    template_name = 'dashboard_pages/document_detail.html'

    @method_decorator(MustLogin)
    def get(self, request, document_id):
        # Get the document
        document = get_object_or_404(Document, id=document_id)
        
        # Check if user has permission to view this document
        if not self.can_view_document(request.user, document):
            raise Http404("Document not found")
        
        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        
        # Prepare file URLs
        for f in document.files.all():
            try:
                f.absolute_url = request.build_absolute_uri(f.file.url)
            except Exception:
                f.absolute_url = f.file.url if hasattr(f, 'file') else ''
        
        context = {
            'document': document,
            'notifications': notifications,
            'notification_count': notification_count,
            'has_change_permission': request.user.has_perm('dashboard.change_document') or request.user.executive_position == "Secretary",
            'has_delete_permission': request.user.has_perm('dashboard.delete_document') or request.user.executive_position == "Secretary",
            'active_menu': 'documents'
        }
        
        return render(request, self.template_name, context)
    
    def can_view_document(self, user, document):
        """Check if user has permission to view this document"""
        if user.is_superuser:
            return True
        
        if document.visibility == 'everyone':
            return True
        
        if document.visibility == 'selected_groups':
            return document.visible_to_groups.filter(id__in=user.groups.all()).exists()
        
        return False
