from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse


from dashboard.models import Document, File

from utag_ug_archiver.utils.decorators import MustLogin

#For File Management
class InternalDocumentsView(View):
    template_name = 'dashboard_pages/internal_documents.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all internal documents
        documents = Document.objects.filter(category='internal')
        context = {
            'documents' : documents
        }
        return render(request, self.template_name, context)
    
class ExternalDocumentsView(View):
    template_name = 'dashboard_pages/external_documents.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all external documents
        documents = Document.objects.filter(category='external')
        context = {
            'documents' : documents
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