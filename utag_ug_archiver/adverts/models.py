from datetime import datetime, timedelta
from django.db import models
from accounts.models import User
import random
from PIL import Image
from django.utils.text import slugify

class Advertiser(models.Model):
    company_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    address = models.CharField(max_length=255)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

def upload_to(instance, filename):
    # Define the path to store the uploaded image
    return f"advertisement_images/{instance.advertiser.company_name}/{filename}"

class Advertisement(models.Model):
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('PUBLISHED', 'Published'),
        ('EXPIRED', 'Expired'),
    )
    POSITION_CHOICES = (
        ('top', 'Top'),
        ('sidebar', 'Sidebar'),
        ('bottom', 'Bottom'),
    )
    advertiser = models.ForeignKey(Advertiser, on_delete=models.CASCADE)
    plan = models.ForeignKey('AdvertPlan', on_delete=models.SET_NULL, blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to=upload_to, blank=True, null=True)
    target_url = models.URLField()
    # Legacy single-position field removed. Use `placements` M2M instead.
    # New richer asset fields
    desktop_image = models.ImageField(upload_to=upload_to, blank=True, null=True)
    mobile_image = models.ImageField(upload_to=upload_to, blank=True, null=True)
    alt_text = models.CharField(max_length=255, blank=True, null=True)
    cta_text = models.CharField(max_length=80, blank=True, null=True)
    html_content = models.TextField(blank=True, null=True)
    impressions_cap = models.PositiveIntegerField(blank=True, null=True)
    impressions_count = models.PositiveIntegerField(default=0)
    priority = models.SmallIntegerField(default=0, help_text="Higher value = higher priority when rendering")
    # Flexible placement relation (recommended)
    placements = models.ManyToManyField('Placement', blank=True, related_name='adverts')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    clicks = models.PositiveIntegerField(default=0)
    
    def clicked(self):
        self.clicks += 1
        self.save()

    def increment_impression(self):
        # Respect cap if set
        if self.impressions_cap is None or self.impressions_count < self.impressions_cap:
            self.impressions_count += 1
            self.save(update_fields=['impressions_count'])
    
    def __str__(self):
        return f"{self.advertiser.company_name} - {self.start_date} to {self.end_date}"
    
    def get_image_url(self):
        # Prefer desktop -> legacy image -> mobile -> image_url
        if self.desktop_image:
            return self.desktop_image.url
        if self.image:
            return self.image.url
        if self.mobile_image:
            return self.mobile_image.url
        return self.image_url
    
    def get_image_dimensions(self):
        if self.image:
            with Image.open(self.image) as img:
                return img.width, img.height
        return None, None
    
    @property
    def image_width(self):
        width, _ = self.get_image_dimensions()
        return width

    @property
    def image_height(self):
        _, height = self.get_image_dimensions()
        return height

    def save(self, *args, **kwargs):
        # If an image is provided via image_url, clear the image field
        if self.image_url:
            self.image = None
        # Calculate the end date based on the selected plan
        if self.status == "PUBLISHED" and self.start_date and self.plan and self.plan.duration_in_days:
            start_date_obj = datetime.strptime(str(self.start_date), "%Y-%m-%d").date()
            self.end_date = start_date_obj + timedelta(days=self.plan.duration_in_days)
        
        super().save(*args, **kwargs)


class AdvertPlan(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )
    POSITION_CHOICES = (
        ('top', 'Top'),
        ('sidebar', 'Sidebar'),
        ('bottom', 'Bottom'),
    )

    name = models.CharField(max_length=255, unique=True, blank=True, null=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_in_days = models.PositiveIntegerField(blank=True, null=True)
    status = models.CharField(max_length=255, choices=STATUS_CHOICES, default='active')
    # Previously this model stored allowed positions as a CSV string. We moved to Placement model.
    # Keep description and plan metadata here.
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.status})"


class Placement(models.Model):
    """
    Represents a placement/slot where adverts can be shown. Examples: 'top', 'sidebar', 'bottom', 'hero', 'footer'.
    Use a stable key for code/queries and a human friendly name.
    """
    key = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, null=True)
    recommended_width = models.PositiveIntegerField(blank=True, null=True)
    recommended_height = models.PositiveIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.key})"

    @classmethod
    def get_or_create_from_key(cls, key):
        k = slugify(str(key).strip())
        if not k:
            return None
        obj, _ = cls.objects.get_or_create(key=k, defaults={'name': key})
        return obj


    

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('Paid', 'Paid'),
        ('Yet to Pay', 'Yet to Pay'),
    )
    PAYMENT_METHOD_CHOICES = (
        ('Cash', 'Cash'),
    )
    def generate_transaction_id():
        return str(random.randint(1000000000, 9999999999))
    
    transaction_id = models.CharField(max_length=10, unique=True, blank=True, null=True)
    advertiser = models.ForeignKey(Advertiser, on_delete=models.CASCADE)
    plan = models.ForeignKey(AdvertPlan, on_delete=models.CASCADE, related_name='plan')
    advert = models.ForeignKey(Advertisement, on_delete=models.SET_NULL, blank=True, null=True, related_name='payment')
    payment_date = models.DateField(blank=True, null=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_method = models.CharField(max_length=255, choices=PAYMENT_METHOD_CHOICES, default='Cash')
    payment_status = models.CharField(max_length=255, choices=PAYMENT_STATUS_CHOICES, default='Yet to Pay')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        self.transaction_id = Payment.generate_transaction_id()
        super(Payment, self).save(*args, **kwargs)