from django.contrib.auth.hashers import make_password
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.contrib.auth.models import Group
from django.db.models import Q
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
        return render(request, self.template_name, context)

    def get_documents(self, user):
        # Example implementation of get_documents method
        if user.is_superuser:
            return Document.objects.all()
        elif user.groups.filter(name='SomeGroup').exists():
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

        context = {
            'document': document,
            'CATEGORY_CHOICES': Document.CATEGORY_CHOICES,
            'DOCUMENT_STATUS_CHOICES': Document.DOCUMENT_STATUS_CHOICES,
            'VISIBILITY_CHOICES': Document.VISIBILITY_CHOICES,
            'all_groups': Group.objects.all()
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