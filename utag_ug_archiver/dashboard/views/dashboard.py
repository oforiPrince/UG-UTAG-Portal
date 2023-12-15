from datetime import datetime
import random
import string

from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect



from accounts.models import User
from dashboard.models import Executive, Event, Document

from utag_ug_archiver.utils.decorators import MustLogin

class DashboardView(View):
    template_name = 'dashboard_pages/dashboard.html'
    
    @method_decorator(MustLogin)
    def get(self,request):
        total_internal_documents = Document.objects.filter(category='internal').count()
        total_external_documents = Document.objects.filter(category='external').count()
        print(total_external_documents)
        total_executives = Executive.objects.filter(is_active=True).count()
        total_members = User.objects.filter(is_member=True).count()
        total_admins = User.objects.filter(is_admin=True).count()
        total_secretaries = User.objects.filter(is_secretary=True).count()
        published_events = Event.objects.filter(is_published=True).order_by('-date')[:5]
        recent_added_documents = Document.objects.all().order_by('-created_at')[:6]
        context = {
            'total_internal_documents' : total_internal_documents,
            'total_external_documents' : total_external_documents,
            'total_executives' : total_executives,
            'total_members' : total_members,
            'total_admins' :total_admins,
            'total_secretaries': total_secretaries,
            'published_events' : published_events,
            'recent_added_documents' : recent_added_documents
        }
        return render(request, self.template_name, context)