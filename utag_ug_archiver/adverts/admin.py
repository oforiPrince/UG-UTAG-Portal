from django.contrib import admin
from adverts.models import AdvertPlan, Advertiser, Advertisement
# Register your models here.
admin.site.register(Advertiser)
admin.site.register(Advertisement)
admin.site.register(AdvertPlan)
