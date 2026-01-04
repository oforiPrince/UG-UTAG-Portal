from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered
from .models import AdSlot, Ad, AdvertPlan, AdvertOrder


class AdSlotAdmin(admin.ModelAdmin):
    list_display = ('key', 'name', 'width', 'height')
    search_fields = ('key', 'name')


class AdAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'slot', 'created_by', 'active', 'start', 'end', 'priority', 'impressions', 'clicks')
    list_filter = ('active', 'slot')
    search_fields = ('title', 'target_url', 'slot__key')
    readonly_fields = ('impressions', 'clicks', 'created_at', 'updated_at')
    raw_id_fields = ('created_by',)
    fieldsets = (
        (None, {'fields': ('slot', 'title', 'image', 'html_content', 'target_url', 'created_by')}),
        ('Scheduling', {'fields': ('active', 'start', 'end', 'priority')}),
        ('Stats', {'fields': ('impressions', 'clicks', 'created_at', 'updated_at')}),
    )


class AdvertPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_in_days', 'created_by', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name',)
    raw_id_fields = ('created_by',)


class AdvertOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'plan', 'ad', 'status', 'paid', 'created_at')
    list_filter = ('status', 'paid')
    search_fields = ('user__username', 'plan__name')
    raw_id_fields = ('user', 'ad')


for model, admin_class in (
    (AdSlot, AdSlotAdmin),
    (Ad, AdAdmin),
    (AdvertPlan, AdvertPlanAdmin),
    (AdvertOrder, AdvertOrderAdmin),
):
    try:
        admin.site.register(model, admin_class)
    except AlreadyRegistered:
        # Safe to ignore; autoreloader may re-import admin modules during development
        pass


