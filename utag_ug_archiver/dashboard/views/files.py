from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect


from dashboard.models import Document

from utag_ug_archiver.utils.decorators import MustLogin

#For File Management
class InternalDocumentsView(View):
    template_name = 'dashboard_pages/internal_documents.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all internal documents
        internal_documents = Document.objects.filter(category='internal')
        context = {
            'internal_documents' : internal_documents
        }
        return render(request, self.template_name, context)
    
class ExternalDocumentsView(View):
    template_name = 'dashboard_pages/external_documents.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all external documents
        external_documents = Document.objects.filter(category='external')
        context = {
            'external_documents' : external_documents
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
        description = request.POST.get('description')
        file = request.FILES.get('file')
        category = 'internal'
        #Create the document
        document = Document.objects.create(title=title, description=description, file=file, category=category)
        #Save the document
        document.save()
        messages.success(request, 'Document added successfully')
        return redirect('internal_documents')