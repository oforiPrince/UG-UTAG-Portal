from django.contrib.auth.hashers import make_password
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse


from dashboard.models import Announcement, Document, File

from utag_ug_archiver.utils.decorators import MustLogin

#For File Management
class DocumentsView(View):
    template_name = 'dashboard_pages/documents.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all Documents
        documents = Document.objects.all().order_by('-id')
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
            'documents' : documents,
            'new_announcements' : new_announcements,
            'announcement_count' : announcement_count
        }
        return render(request, self.template_name, context)
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
    
class UpdateFileView(View):    
    @method_decorator(MustLogin)
    def post(self, request):
        #Get the form data
        document_id = request.POST.get('document_id')
        document = Document.objects.get(pk=document_id)
        title = request.POST.get('title')
        sender = request.POST.get('sender')
        receiver = request.POST.get('receiver')
        date = request.POST.get('date')
        description = request.POST.get('description')
        files = request.FILES.getlist('files')
        
        #Update the document
        document.title = title
        document.sender = sender
        document.receiver = receiver
        document.date = date if date else document.date
        document.description = description
        document.save()
        
        # Create the file
        if files:
            for file in files:
                file = File.objects.create(file=file)
                file.save()
                document.files.add(file)
        
        #Save the document
        document.save()
        messages.success(request, 'Document updated successfully')
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
        document.uploaded_by = request.user

        if document_id:
            document.save()  # Save the document to update it

        files = request.FILES.getlist('files')
        if files:
            for file in files:
                new_file = File(file=file)
                new_file.save()
                document.files.add(new_file)

        document.save()
        messages.success(request, success_message)
        return redirect('dashboard:documents') 