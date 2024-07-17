from django.contrib.auth.hashers import make_password
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse


from dashboard.models import Announcement, Document, File

from utag_ug_archiver.utils.decorators import MustLogin

#For File Management
class InternalDocumentsView(View):
    template_name = 'dashboard_pages/internal_documents.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all internal documents
        documents = Document.objects.filter(category='internal')
        if request.user.is_admin:
            new_announcements = Announcement.objects.filter(status='PUBLISHED').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').count()
        elif request.user.is_secretary or request.user.is_executive:
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='MEMBERS').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='MEMBERS').order_by('-created_at')[:3]
        elif request.user.is_member:
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='EXECUTIVES').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='EXECUTIVES').order_by('-created_at')[:3]
        context = {
            'documents' : documents,
            'new_announcements' : new_announcements,
            'announcement_count' : announcement_count
        }
        return render(request, self.template_name, context)
    
class ExternalDocumentsView(View):
    template_name = 'dashboard_pages/external_documents.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all external documents
        documents = Document.objects.filter(category='external')
        if request.user.is_admin:
            new_announcements = Announcement.objects.filter(status='PUBLISHED').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').count()
        elif request.user.is_secretary or request.user.is_executive:
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='MEMBERS').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='MEMBERS').order_by('-created_at')[:3]
        elif request.user.is_member:
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='EXECUTIVES').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='EXECUTIVES').order_by('-created_at')[:3]
        context = {
            'documents' : documents,
            'new_announcements' : new_announcements,
            'announcement_count': announcement_count
        }
        return render(request, self.template_name, context)

class AddInternalDocumentView(View):
    template_name = 'dashboard_pages/add_internal_files.html'
    @method_decorator(MustLogin)
    def get(self, request):
        return render(request, self.template_name)
    
    @method_decorator(MustLogin)
    def post(self, request):
        #Get the form data
        title = request.POST.get('title')
        sender = request.POST.get('sender')
        receiver = request.POST.get('receiver')
        date = request.POST.get('date')
        description = request.POST.get('description')
        files = request.FILES.getlist('files')
        category = 'internal'
        #Create the document
        document = Document.objects.create(title=title, description=description, category=category, sender=sender, receiver=receiver, uploaded_by=request.user, date=date)
        # Create the file
        for file in files:
            file = File.objects.create(file=file)
            file.save()
            document.files.add(file)

        #Save the document
        document.save()
        messages.success(request, 'Document added successfully')
        return redirect('dashboard:internal_documents')
    
class DeleteFileView(View):
    def post(self, request):
        file_id = request.POST.get('file_id')
        print(file_id)
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
    
class AddExternalDocumentView(View):
    template_name = 'dashboard_pages/add_external_files.html'
    @method_decorator(MustLogin)
    def get(self, request):
        return render(request, self.template_name)
    
    @method_decorator(MustLogin)
    def post(self, request):
        #Get the form data
        title = request.POST.get('title')
        sender = request.POST.get('sender')
        receiver = request.POST.get('receiver')
        date = request.POST.get('date')
        description = request.POST.get('description')
        files = request.FILES.getlist('files')
        category = 'external'
        #Create the document
        document = Document.objects.create(title=title, description=description, category=category, sender=sender, receiver=receiver, uploaded_by=request.user, date=date)
        # Create the file
        for file in files:
            file = File.objects.create(file=file)
            file.save()
            document.files.add(file)

        #Save the document
        document.save()
        messages.success(request, 'Document added successfully')
        return redirect('dashboard:external_documents')
    
class DocumentCreateUpdateView(View):
    template_name = 'dashboard_pages/forms/create_update_document.html'

    def get(self, request, pk=None):
        if pk:
            document = get_object_or_404(Document, pk=pk)
        else:
            document = None

        context = {
            'document': document,
            'CATEGORY_CHOICES': Document.CATEGORY_CHOICES,
            'DOCUMENT_STATUS_CHOICES': Document.DOCUMENT_STATUS_CHOICES,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk=None):
        if pk:
            document = get_object_or_404(Document, pk=pk)
        else:
            document = Document()

        document.title = request.POST.get('title')
        document.sender = request.POST.get('sender')
        document.receiver = request.POST.get('receiver')
        document.category = request.POST.get('category')
        document.date = request.POST.get('date')
        document.description = request.POST.get('description')
        document.status = request.POST.get('status')
        document.uploaded_by = request.user

        if pk:
            document.save()  # Save the document to update it

        files = request.FILES.getlist('files')
        for file in files:
            new_file = File(file=file)
            new_file.save()
            document.files.add(new_file)

        document.save()

        return redirect('dashboard:documents') 