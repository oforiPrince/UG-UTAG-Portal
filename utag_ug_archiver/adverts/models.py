from django.db import models
from django.utils import timezone
from django.conf import settings
import os


def ad_upload_to(instance, filename):
    # store in media/advertisement_images/<slot_key>/<filename>
    slot = getattr(instance, 'slot', None)
    key = slot.key if slot else 'general'
    return f"advertisement_images/{key}/{filename}"

# Backwards-compatible alias for older migrations that imported `upload_to`
def upload_to(instance, filename):
    return ad_upload_to(instance, filename)


class AdSlot(models.Model):
    """A named placement on the site where ads can be displayed.

    Examples: header_728x90, sidebar_300x250, footer_banner.
    The `key` is used in templates and template tags to fetch the correct slot.
    """
    key = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    width = models.PositiveIntegerField(blank=True, null=True)
    height = models.PositiveIntegerField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['key']

    def __str__(self) -> str:
        return f"{self.name} ({self.key})"


class Ad(models.Model):
    """A simple, modern ad model.

    Fields:
    - slot: which AdSlot this ad belongs to
    - image: optional image to show
    - html_content: optional rich html for advanced creatives
    - target_url: where clicks should go
    - active / start / end: scheduling
    - priority: higher shows first when multiple active
    - impressions, clicks: counters
    """
    slot = models.ForeignKey(AdSlot, on_delete=models.CASCADE, related_name='ads')
    title = models.CharField(max_length=140, blank=True)
    image = models.ImageField(upload_to=ad_upload_to, blank=True, null=True)
    html_content = models.TextField(blank=True, null=True)
    target_url = models.URLField(blank=True, null=True)

    active = models.BooleanField(default=True)
    start = models.DateTimeField(blank=True, null=True)
    end = models.DateTimeField(blank=True, null=True)
    priority = models.SmallIntegerField(default=0, help_text='Higher number = higher priority')

    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Who uploaded/created this ad (optional for backward compatibility)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_ads')

    class Meta:
        ordering = ['-priority', '-created_at']

    def __str__(self) -> str:
        return self.title or f"Ad #{self.pk} ({self.slot.key})"

    def is_live(self) -> bool:
        """Return True if the ad should be displayed now."""
        if not self.active:
            return False
        now = timezone.now()
        if self.start and now < self.start:
            return False
        if self.end and now > self.end:
            return False
        return True

    def save(self, *args, **kwargs):
        # Optimize image on upload
        from utag_ug_archiver.utils.image_optimizer import ImageOptimizer
        if self.pk:
            try:
                old_instance = Ad.objects.get(pk=self.pk)
                if self.image and old_instance.image != self.image:
                    if hasattr(self.image, 'file'):
                        optimized = ImageOptimizer.optimize_image(
                            self.image,
                            image_type='default',
                            max_size_kb=400
                        )
                        if optimized:
                            self.image.save(
                                self.image.name,
                                optimized,
                                save=False
                            )
            except Ad.DoesNotExist:
                pass
        else:
            if self.image and hasattr(self.image, 'file'):
                optimized = ImageOptimizer.optimize_image(
                    self.image,
                    image_type='default',
                    max_size_kb=400
                )
                if optimized:
                    self.image.save(
                        self.image.name,
                        optimized,
                        save=False
                    )
        
        super().save(*args, **kwargs)

    @property
    def get_image_url(self):
        """Safe image URL accessor for templates; returns None when missing."""
        try:
            if self.image and hasattr(self.image, 'url'):
                return self.image.url
        except Exception:
            return None
        return None

    @property
    def get_image_dimensions(self):
        """Return (width, height) if available, else (None, None)."""
        try:
            if self.image and hasattr(self.image, 'width') and hasattr(self.image, 'height'):
                return (self.image.width, self.image.height)
        except Exception:
            pass
        return (None, None)

    def get_status_display(self):
        """Return a human readable status based on active flag and dates."""
        now = timezone.now()
        if not self.active:
            return 'Draft'
        if self.end and self.end < now:
            return 'Expired'
        if self.start and self.start > now:
            return 'Scheduled'
        return 'Published'

    def click(self):
        # use F() expression to avoid race conditions
        from django.db.models import F

        self.__class__.objects.filter(pk=self.pk).update(clicks=F('clicks') + 1)

    def impression(self):
        from django.db.models import F
        # single atomic increment
        self.__class__.objects.filter(pk=self.pk).update(impressions=F('impressions') + 1)


class AdvertPlan(models.Model):
    """Minimal Advertisement Plan model for pricing and duration catalog.
    Moved from `dashboard.models` to centralize adverts-related models in the
    `adverts` app.
    """
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration_in_days = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Who created/defined this plan
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_advert_plans')

    def __str__(self):
        return self.name

    @property
    def uploaded_by_name(self):
        """Return a human friendly name for the uploader or 'N/A' if missing."""
        user = getattr(self, 'created_by', None)
        if not user:
            return 'N/A'
        # Prefer full name if available
        try:
            full_name = user.get_full_name()
        except Exception:
            full_name = None
        if full_name:
            return full_name
        # Fallback to username or string representation
        return getattr(user, 'username', str(user))

    @property
    def category_label(self):
        """Return human readable category label."""
        try:
            return self.get_category_display()
        except Exception:
            return getattr(self, 'category', 'N/A')

    @property
    def status_label(self):
        """Return human readable status label."""
        try:
            return self.get_status_display()
        except Exception:
            return self.status or 'N/A'


class AdvertOrder(models.Model):
    """Record of a user registering/purchasing an advert plan.

    - user: who placed the order (required)
    - plan: the AdvertPlan purchased
    - ad: optional Ad object (if the user uploaded or selected an ad at registration)
    - created_at: time of registration
    - status: workflow status (pending, active, cancelled)
    - paid: whether payment is complete
    - start_date / end_date: computed or set to represent the active window
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='advert_orders')
    plan = models.ForeignKey(AdvertPlan, on_delete=models.PROTECT, related_name='orders')
    ad = models.ForeignKey(Ad, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    paid = models.BooleanField(default=False)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Order #{self.pk} - {self.user} -> {self.plan.name} ({self.status})"

    def activate(self):
        """Mark order active and set start/end dates based on plan duration if not set."""
        if not self.start_date:
            self.start_date = timezone.now().date()
        if not self.end_date and self.plan and self.plan.duration_in_days:
            self.end_date = self.start_date + timezone.timedelta(days=self.plan.duration_in_days)
        self.status = 'active'
        self.paid = True
        self.save(update_fields=['start_date', 'end_date', 'status', 'paid'])

