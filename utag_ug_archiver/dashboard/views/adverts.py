from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect



from adverts.models import AdvertPlan, Advertisement, Advertiser

from utag_ug_archiver.utils.decorators import MustLogin
class AdvertsView(View):
    template_name = 'dashboard_pages/adverts.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all adverts
        adverts = Advertisement.objects.all()
        context = {
            'adverts' : adverts
        }
        return render(request, self.template_name, context)
    
class AdvertPlansView(View):
    template_name = 'dashboard_pages/advert_plans.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all advert plans
        plans = AdvertPlan.objects.all()
        context = {
            'plans' : plans
        }
        return render(request, self.template_name, context)
    
class CompaniesView(View):
    template_name = 'dashboard_pages/advert_companies.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all companies
        companies = Advertiser.objects.all()
        context = {
            'companies' : companies
        }
        return render(request, self.template_name, context)