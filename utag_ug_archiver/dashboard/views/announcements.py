from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect



from dashboard.models import Announcement

from utag_ug_archiver.utils.decorators import MustLogin

class AnnouncementsView(View):
    template_name = 'dashboard_pages/announcements.html'
    def get(self, request):
        announcements = Announcement.objects.all().order_by('-created_at')
        context = {
            'announcements' : announcements,
        }
        return render(request, self.template_name, context)