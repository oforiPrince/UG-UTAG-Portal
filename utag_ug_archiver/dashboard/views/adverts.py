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
        advertisers = Advertiser.objects.all()
        active_plans = AdvertPlan.objects.filter(status='active')
        context = {
            'adverts' : adverts,
            'advertisers' : advertisers,
            'plans' : active_plans
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
    
class AdvertCreateView(View):    
    @method_decorator(MustLogin)
    def post(self, request):
        image = request.FILES.get('image')
        start_date = request.POST.get('start_date')
        plan_id = request.POST.get('plan_id')
        plan = AdvertPlan.objects.get(id=plan_id)
        advertiser_id = request.POST.get('advertiser_id')
        advertiser = Advertiser.objects.get(id=advertiser_id)
        status = request.POST.get('status')
        target_url = request.POST.get('target_url')
        advert = Advertisement.objects.create(
            image = image,
            target_url =target_url,
            start_date = start_date,
            plan = plan,
            advertiser = advertiser,
            status = status,
        )
        messages.success(request, 'Advert added successfully')
        return redirect('dashboard:adverts')
    
class AdvertUpdateView(View):    
    @method_decorator(MustLogin)
    def post(self, request):
        advert_id = request.POST.get('advert_id')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        plan = request.POST.get('plan')
        advertiser = request.POST.get('advertiser')
        status = request.POST.get('status')
        advert = Advertisement.objects.get(id=advert_id)
        advert.start_date = start_date
        advert.end_date = end_date
        advert.plan = plan
        advert.advertiser = advertiser
        advert.status = status
        advert.save()
        messages.success(request, 'Advert updated successfully')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class AdvertDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, advert_id):
        advert = Advertisement.objects.get(id=advert_id)
        advert.delete()
        messages.success(request, 'Advert deleted successfully')
        return redirect('dashboard:adverts')
    
class AdvertPlanCreateView(View):    
    @method_decorator(MustLogin)
    def post(self, request):
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        duration_in_days = request.POST.get('duration_in_days')
        status = request.POST.get('status')
        plan = AdvertPlan.objects.create(
            name = name,
            description = description,
            price = price,
            duration_in_days = duration_in_days,
            status = status
        )
        messages.success(request, 'Advert plan added successfully')
        return redirect('dashboard:plans')
    
class AdvertPlanUpdateView(View):
    @method_decorator(MustLogin)
    def post(self, request):
        plan_id = request.POST.get('plan_id')
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        duration_in_days = request.POST.get('duration_in_days')
        status = request.POST.get('status')
        plan = AdvertPlan.objects.get(id=plan_id)
        plan.name = name
        plan.description = description
        plan.price = price
        plan.duration_in_days = duration_in_days
        plan.status = status
        plan.save()
        messages.success(request, 'Advert plan updated successfully')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class AdvertPlanDeleteView(View):    
    @method_decorator(MustLogin)
    def get(self, request, plan_id):
        plan = AdvertPlan.objects.get(id=plan_id)
        plan.delete()
        messages.success(request, 'Advert plan deleted successfully')
        return redirect('dashboard:plans')
    
class CompanyCreateView(View):    
    @method_decorator(MustLogin)
    def post(self, request):
        advertiser_name = request.POST.get('advertiser_name')
        contact_name = request.POST.get('contact_name')
        advertiser_email = request.POST.get('email')
        advertiser_phone = request.POST.get('phone_number')
        advertiser_address = request.POST.get('address')
        advertiser = Advertiser.objects.create(
            advertiser_name = advertiser_name,
            contact_name = contact_name,
            email = advertiser_email,
            phone_number = advertiser_phone,
            address = advertiser_address
        )
        messages.success(request, 'Company added successfully')
        return redirect('dashboard:companies')
    
class CompanyUpdateView(View):
    @method_decorator(MustLogin)
    def post(self, request):
        advertiser_id = request.POST.get('advertiser_id')
        advertiser_name = request.POST.get('advertiser_name')
        contact_name = request.POST.get('contact_name')
        advertiser_email = request.POST.get('email')
        advertiser_phone = request.POST.get('phone_number')
        advertiser_address = request.POST.get('address')
        advertiser = Advertiser.objects.get(id=advertiser_id)
        advertiser.advertiser_name = advertiser_name
        advertiser.contact_name = contact_name
        advertiser.email = advertiser_email
        advertiser.phone_number = advertiser_phone
        advertiser.address = advertiser_address
        advertiser.save()
        messages.success(request, 'Company updated successfully')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class CompanyDeleteView(View):    
    @method_decorator(MustLogin)
    def get(self, request, advertiser_id):
        advertiser = Advertiser.objects.get(id=advertiser_id)
        advertiser.delete()
        messages.success(request, 'Company deleted successfully')
        return redirect('dashboard:companies')