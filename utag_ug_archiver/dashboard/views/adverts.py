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
    
class AdvertCreateView(View):    
    @method_decorator(MustLogin)
    def post(self, request):
        title = request.POST.get('title')
        content = request.POST.get('content')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        plan = request.POST.get('plan')
        company = request.POST.get('company')
        status = request.POST.get('status')
        created_by = request.user
        advert = Advertisement.objects.create(
            title = title,
            content = content,
            start_date = start_date,
            end_date = end_date,
            plan = plan,
            company = company,
            status = status,
            created_by = created_by
        )
        messages.success(request, 'Advert added successfully')
        return redirect('dashboard:adverts')
    
class AdvertUpdateView(View):    
    @method_decorator(MustLogin)
    def post(self, request):
        advert_id = request.POST.get('advert_id')
        title = request.POST.get('title')
        content = request.POST.get('content')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        plan = request.POST.get('plan')
        company = request.POST.get('company')
        status = request.POST.get('status')
        advert = Advertisement.objects.get(id=advert_id)
        advert.title = title
        advert.content = content
        advert.start_date = start_date
        advert.end_date = end_date
        advert.plan = plan
        advert.company = company
        advert.status = status
        advert.save()
        messages.success(request, 'Advert updated successfully')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
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
        company_name = request.POST.get('company_name')
        company_email = request.POST.get('company_email')
        company_phone = request.POST.get('company_phone')
        company_address = request.POST.get('company_address')
        company = Advertiser.objects.create(
            company_name = company_name,
            company_email = company_email,
            company_phone = company_phone,
            company_address = company_address
        )
        messages.success(request, 'Company added successfully')
        return redirect('dashboard:companies')
    
class CompanyUpdateView(View):
    @method_decorator(MustLogin)
    def post(self, request):
        company_id = request.POST.get('company_id')
        company_name = request.POST.get('company_name')
        company_email = request.POST.get('company_email')
        company_phone = request.POST.get('company_phone')
        company_address = request.POST.get('company_address')
        company = Advertiser.objects.get(id=company_id)
        company.company_name = company_name
        company.company_email = company_email
        company.company_phone = company_phone
        company.company_address = company_address
        company.save()
        messages.success(request, 'Company updated successfully')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class CompanyDeleteView(View):    
    @method_decorator(MustLogin)
    def get(self, request, company_id):
        company = Advertiser.objects.get(id=company_id)
        company.delete()
        messages.success(request, 'Company deleted successfully')
        return redirect('dashboard:companies')