from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect



from dashboard.models import News

from utag_ug_archiver.utils.decorators import MustLogin

class NewsView(View):
    template_name = 'dashboard_pages/news.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all news
        news = News.objects.all()
        context = {
            'newss' : news
        }
        return render(request, self.template_name, context)