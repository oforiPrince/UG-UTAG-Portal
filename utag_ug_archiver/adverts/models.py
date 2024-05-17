from datetime import datetime, timedelta
from django.db import models
from accounts.models import User
import random
from PIL import Image

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
    advertiser = models.ForeignKey(Advertiser, on_delete=models.CASCADE)
    plan = models.ForeignKey('AdvertPlan', on_delete=models.SET_NULL, blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to=upload_to, blank=True, null=True)
    target_url = models.URLField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    clicks = models.PositiveIntegerField(default=0)
    
    def clicked(self):
        self.clicks += 1
        self.save()
    
    def __str__(self):
        return f"{self.advertiser.company_name} - {self.start_date} to {self.end_date}"
    
    def get_image_url(self):
        if self.image:
            return self.image.url
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
    name = models.CharField(max_length=255, unique=True, blank=True, null=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_in_days = models.PositiveIntegerField(blank=True, null=True)
    status = models.CharField(max_length=255, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)

    

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