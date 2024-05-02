from django.db import models

class Advertiser(models.Model):
    company_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255)
    email = models.EmailField()

def upload_to(instance, filename):
    # Define the path to store the uploaded image
    return f"advertisement_images/{instance.advertiser.company_name}/{filename}"

class Advertisement(models.Model):
    advertiser = models.ForeignKey(Advertiser, on_delete=models.CASCADE)
    image_url = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to=upload_to, blank=True, null=True)
    target_url = models.URLField()
    start_date = models.DateField()
    end_date = models.DateField()
    
    def __str__(self):
        return f"{self.advertiser.company_name} - {self.start_date} to {self.end_date}"
    
    def get_image_url(self):
        if self.image:
            return self.image.url
        return self.image_url

    def save(self, *args, **kwargs):
        # If an image is provided via image_url, clear the image field
        if self.image_url:
            self.image = None
        super().save(*args, **kwargs)
