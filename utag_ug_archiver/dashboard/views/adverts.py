from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from adverts.models import AdvertPlan, Advertisement, Advertiser

from dashboard.models import Announcement, Notification
from utag_ug_archiver.utils.decorators import MustLogin

class AdvertsView(PermissionRequiredMixin, View):
    template_name = 'dashboard_pages/adverts.html'
    permission_required = 'adverts.view_advertisement'
    
    @method_decorator(MustLogin)
    def get(self, request):
        # Get all adverts
        adverts = Advertisement.objects.all()
        advertisers = Advertiser.objects.all()
        active_plans = AdvertPlan.objects.filter(status='active')
        
        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()

        # Prepare context
        context = {
            'adverts': adverts,
            'advertisers': advertisers,
            'plans': active_plans,
            'notification_count': notification_count,
            'notifications': notifications,
        }

        # Render the template
        return render(request, self.template_name, context)
    
class AdvertPlansView(PermissionRequiredMixin, View):
    permission_required = 'adverts.view_advertplan'
    template_name = 'dashboard_pages/advert_plans.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all advert plans
        plans = AdvertPlan.objects.all()
        
         # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        context = {
            'plans' : plans,
            'notification_count' : notification_count,
            'notifications' : notifications
        }
        return render(request, self.template_name, context)
    
class CompaniesView(PermissionRequiredMixin, View):
    permission_required = 'adverts.view_advertiser'
    template_name = 'dashboard_pages/advert_companies.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all companies
        companies = Advertiser.objects.all()
         # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        
        context = {
            'companies' : companies,
            'notification_count' : notification_count,
            'notifications' : notifications
        }
        return render(request, self.template_name, context)
    
class AdvertCreateView(PermissionRequiredMixin, View):
    permission_required = 'adverts.add_advertisement'

    @method_decorator(MustLogin)
    def post(self, request):
        # Retrieve form data
        image = request.FILES.get('image')
        start_date = request.POST.get('start_date')
        plan_id = request.POST.get('plan_id')
        position = request.POST.get('position')  # Retrieve selected position
        advertiser_id = request.POST.get('advertiser_id')
        status = request.POST.get('status')
        target_url = request.POST.get('target_url')

        # Validate plan and advertiser
        try:
            plan = AdvertPlan.objects.get(id=plan_id)
            advertiser = Advertiser.objects.get(id=advertiser_id)
        except (AdvertPlan.DoesNotExist, Advertiser.DoesNotExist):
            messages.error(request, 'Invalid Plan or Advertiser.')
            return redirect('dashboard:adverts')

        # Validate position
        valid_positions = plan.positions.split(',')  # Retrieve allowed positions for the plan
        if position not in valid_positions:
            messages.error(request, f"The position '{position}' is not allowed for the selected plan.")
            return redirect('dashboard:adverts')

        # Create the advertisement
        advert = Advertisement.objects.create(
            image=image,
            target_url=target_url,
            start_date=start_date,
            plan=plan,
            advertiser=advertiser,
            position=position,  # Save the selected position
            status=status,
        )

        # Success message and redirect
        messages.success(request, 'Advert added successfully')
        return redirect('dashboard:adverts')

    
class AdvertUpdateView(PermissionRequiredMixin, View):
    permission_required = 'adverts.change_advertisement'    
    @method_decorator(MustLogin)
    def post(self, request):
        advert_id = request.POST.get('advert_id')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        plan_id = request.POST.get('plan_id')
        advertiser_id = request.POST.get('advertiser_id')
        status = request.POST.get('status')
        advert = Advertisement.objects.get(id=advert_id)
        plan= AdvertPlan.objects.get(id=plan_id)
        advertiser = Advertiser.objects.get(id=advertiser_id)
        advert.start_date = start_date
        advert.plan = plan
        advert.advertiser = advertiser
        advert.status = status
        advert.save()
        messages.success(request, 'Advert updated successfully')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class AdvertDeleteView(PermissionRequiredMixin, View):
    permission_required = 'adverts.delete_advertisement'
    @method_decorator(MustLogin)
    def get(self, request, advert_id):
        advert = Advertisement.objects.get(id=advert_id)
        advert.delete()
        messages.success(request, 'Advert deleted successfully')
        return redirect('dashboard:adverts')
    
class AdvertPlanCreateView(PermissionRequiredMixin, View):
    permission_required = 'adverts.add_advertplan'
    
    @method_decorator(MustLogin)
    def post(self, request):
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        duration_in_days = request.POST.get('duration_in_days')
        status = request.POST.get('status')
        
        # Get selected positions from checkboxes
        positions = request.POST.getlist('positions')  # List of selected positions
        
        # Join positions into a comma-separated string for storage
        positions_str = ','.join(positions)
        
        # Create the advert plan
        plan = AdvertPlan.objects.create(
            name=name,
            description=description,
            price=price,
            duration_in_days=duration_in_days,
            status=status,
            positions=positions_str
        )
        
        messages.success(request, 'Advert plan added successfully')
        return redirect('dashboard:plans')

    
class AdvertPlanUpdateView(PermissionRequiredMixin, View):
    permission_required = 'adverts.change_advertplan'
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
    
class AdvertPlanDeleteView(PermissionRequiredMixin, View):
    permission_required = 'adverts.delete_advertplan'    
    @method_decorator(MustLogin)
    def get(self, request, plan_id):
        plan = AdvertPlan.objects.get(id=plan_id)
        plan.delete()
        messages.success(request, 'Advert plan deleted successfully')
        return redirect('dashboard:plans')
    
class CompanyCreateView(PermissionRequiredMixin, View):
    permission_required = 'adverts.add_advertiser'    
    @method_decorator(MustLogin)
    def post(self, request):
        company_name = request.POST.get('company_name')
        contact_name = request.POST.get('contact_name')
        advertiser_email = request.POST.get('email')
        advertiser_phone = request.POST.get('phone_number')
        advertiser_address = request.POST.get('address')
        created_by = request.user
        advertiser = Advertiser.objects.create(
            company_name = company_name,
            contact_name = contact_name,
            email = advertiser_email,
            phone_number = advertiser_phone,
            address = advertiser_address,
            created_by = created_by
        )
        messages.success(request, 'Company added successfully')
        return redirect('dashboard:companies')
    
class CompanyUpdateView(PermissionRequiredMixin, View):
    permission_required = 'adverts.change_advertiser'
    @method_decorator(MustLogin)
    def post(self, request):
        advertiser_id = request.POST.get('advertiser_id')
        advertiser_name = request.POST.get('advertiser_name')
        contact_name = request.POST.get('contact_name')
        advertiser_email = request.POST.get('email')
        advertiser_phone = request.POST.get('phone_number')
        advertiser_address = request.POST.get('address')
        advertiser = Advertiser.objects.get(id=advertiser_id)
        advertiser.company_name = advertiser_name
        advertiser.contact_name = contact_name
        advertiser.email = advertiser_email
        advertiser.phone_number = advertiser_phone
        advertiser.address = advertiser_address
        advertiser.save()
        messages.success(request, 'Company updated successfully')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class CompanyDeleteView(PermissionRequiredMixin, View):
    permission_required = 'adverts.delete_advertiser'    
    @method_decorator(MustLogin)
    def get(self, request, advertiser_id):
        advertiser = Advertiser.objects.get(id=advertiser_id)
        advertiser.delete()
        messages.success(request, 'Company deleted successfully')
        return redirect('dashboard:companies')