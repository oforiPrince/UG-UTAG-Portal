from django.contrib import admin
from .models import Placement, Advertisement, AdvertPlan, Advertiser


@admin.register(Placement)
class PlacementAdmin(admin.ModelAdmin):
    list_display = ('key', 'name', 'recommended_width', 'recommended_height', 'created_at')
    search_fields = ('key', 'name')
    list_filter = ('created_at',)


# @admin.register(Advertiser)
# class AdvertiserAdmin(admin.ModelAdmin):
#     list_display = ('company_name', 'contact_name', 'email', 'phone_number')
#     search_fields = ('company_name', 'contact_name', 'email')


@admin.register(AdvertPlan)
class AdvertPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_in_days', 'status')
    search_fields = ('name',)


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ('advertiser', 'plan', 'start_date', 'end_date', 'status', 'priority')
    search_fields = ('advertiser__company_name', 'target_url')
    list_filter = ('status', 'plan')

