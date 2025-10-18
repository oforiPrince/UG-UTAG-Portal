from django.db import models
from django.contrib.auth.models import Group
from django.utils.text import slugify
from tinymce.models import HTMLField
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
import datetime


class EventSpeaker(models.Model):
    """Model for event speakers"""
    name = models.CharField(max_length=100)
    title = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    presentation_title = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to='event_speakers/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return self.name
        
    class Meta:
        ordering = ['order']

class EventScheduleItem(models.Model):
    """Model for individual event schedule items"""
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='schedule_items')
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    date = models.DateField()
    location = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"{self.title} - {self.date} {self.start_time}"
    
    class Meta:
        ordering = ['date', 'start_time']

class EventDocument(models.Model):
    """Model for event-related documents"""
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=100)
    file = models.FileField(upload_to='event_documents/')
    is_public = models.BooleanField(default=True)
    
    def __str__(self):
        return self.title

class EventImage(models.Model):
    """Model for additional event images"""
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='additional_images')
    image = models.ImageField(upload_to='event_images/gallery/')
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"Image for {self.event.title}"

class Event(models.Model):
    """Enhanced Event model with support for online events"""
    EVENT_STATUS_CHOICES = (
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('postponed', 'Postponed'),
    )
    
    EVENT_TYPE_CHOICES = (
        ('conference', 'Conference'),
        ('workshop', 'Workshop'),
        ('meeting', 'Meeting'),
        ('seminar', 'Seminar'),
        ('lecture', 'Lecture'),
        ('social', 'Social Event'),
        ('online', 'Online Event'),
        ('other', 'Other'),
    )
    
    # Basic Information
    title = models.CharField(max_length=100)
    event_slug = models.SlugField(max_length=100, unique=True, blank=True)
    short_description = models.TextField(help_text="Brief description for listings (max 200 chars)", max_length=200)
    description = HTMLField(help_text="Full event description")
    
    # Featured image
    featured_image = models.ImageField(upload_to='event_images/')
    
    # Date and Time
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    registration_deadline = models.DateTimeField(blank=True, null=True)
    
    # Location
    venue = models.CharField(max_length=100, blank=True, help_text="Leave blank for online events")
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    location_url = models.URLField(blank=True, help_text="Google Maps URL or similar")
    
    # Online Event Details
    is_online = models.BooleanField(default=False, help_text="Check if the event is online")
    online_platform = models.CharField(max_length=100, blank=True, help_text="e.g., Zoom, Microsoft Teams")
    online_link = models.URLField(blank=True, help_text="Link to join the online event")
    access_code = models.CharField(max_length=100, blank=True, help_text="Access code for the online event")
    
    # Event details
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='meeting')
    status = models.CharField(max_length=20, choices=EVENT_STATUS_CHOICES, default='upcoming')
    expected_participants = models.PositiveIntegerField(default=0, blank=True)
    cpd_credits = models.DecimalField(max_digits=5, decimal_places=2, default=0, blank=True, 
                                     help_text="Continuing Professional Development credits")
    
    # Registration
    registration_required = models.BooleanField(default=False)
    registration_url = models.URLField(blank=True, help_text="External registration link if applicable")
    max_participants = models.PositiveIntegerField(default=0, blank=True, 
                                                help_text="0 means unlimited")
    
    # Organizing information
    organizer_name = models.CharField(max_length=100, blank=True)
    organizer_email = models.EmailField(blank=True)
    organizer_phone = models.CharField(max_length=20, blank=True)
    
    # Related models
    speakers = models.ManyToManyField(EventSpeaker, blank=True, related_name='events')
    tags = models.ManyToManyField('Tag', blank=True)
    
    # Publication status
    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    
    # Metadata
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date', '-start_time']
        verbose_name = "Event"
        verbose_name_plural = "Events"
    
    def get_featured_image_url(self):
        return self.featured_image.url if self.featured_image else None
    
    def is_past_due(self):
        end_date = self.end_date
        if isinstance(end_date, str):
            from datetime import date
            end_date = date.fromisoformat(end_date) if end_date else None
        if end_date:
            return end_date < timezone.now().date()
        start_date = self.start_date
        if isinstance(start_date, str):
            from datetime import date
            start_date = date.fromisoformat(start_date)
        return start_date < timezone.now().date()
    
    def is_registration_open(self):
        if not self.registration_required:
            return False
        if self.registration_deadline:
            return timezone.now() < self.registration_deadline
        start_date = self.start_date
        if isinstance(start_date, str):
            from datetime import date
            start_date = date.fromisoformat(start_date)
        return start_date > timezone.now().date()
    
    def get_status_display(self):
        now = timezone.now()

        # Handle case where fields might be strings (during form processing)
        start_date = self.start_date
        if isinstance(start_date, str):
            from datetime import date
            start_date = date.fromisoformat(start_date)
        start_time = self.start_time
        if isinstance(start_time, str):
            from datetime import time
            start_time = time.fromisoformat(start_time) if start_time else None

        end_date = self.end_date
        if isinstance(end_date, str):
            from datetime import date
            end_date = date.fromisoformat(end_date) if end_date else None
        end_time = self.end_time
        if isinstance(end_time, str):
            from datetime import time
            end_time = time.fromisoformat(end_time) if end_time else None

        # Create datetime objects for start and end by combining date and time
        if start_time:
            start_datetime = timezone.make_aware(
                datetime.datetime.combine(start_date, start_time)
            )
        else:
            # For all-day events, start at beginning of start_date
            start_datetime = timezone.make_aware(
                datetime.datetime.combine(start_date, datetime.time(0, 0, 0))
            )

        end_date = end_date or start_date
        if end_time:
            end_datetime = timezone.make_aware(
                datetime.datetime.combine(end_date, end_time)
            )
        else:
            # For all-day events, end at end of end_date
            end_datetime = timezone.make_aware(
                datetime.datetime.combine(end_date, datetime.time(23, 59, 59))
            )

        # Determine status based on datetime comparisons
        if self.is_past_due():
            return 'Past Due'
        if self.status == 'upcoming' and start_datetime and start_datetime > now:
            return 'Upcoming'
        if self.status == 'ongoing' and start_datetime and start_datetime <= now <= (end_datetime or start_datetime):
            return 'Ongoing'
        if self.status == 'completed' and end_datetime and end_datetime < now:
            return 'Completed'
        return self.status
    
    def clean(self):
        start_date = self.start_date
        if isinstance(start_date, str):
            from datetime import date
            start_date = date.fromisoformat(start_date)
        end_date = self.end_date
        if isinstance(end_date, str):
            from datetime import date
            end_date = date.fromisoformat(end_date) if end_date else None
        start_time = self.start_time
        if isinstance(start_time, str):
            from datetime import time
            start_time = time.fromisoformat(start_time) if start_time else None
        end_time = self.end_time
        if isinstance(end_time, str):
            from datetime import time
            end_time = time.fromisoformat(end_time) if end_time else None

        if end_date and end_date < start_date:
            raise ValidationError("End date cannot be before start date")
        if end_time and start_date == end_date and end_time < start_time:
            raise ValidationError("End time cannot be before start time on the same day")
        if self.is_online and not self.online_link:
            raise ValidationError("Online events must have an online link")
    
    def save(self, *args, **kwargs):
        # Auto-generate slug
        if not self.event_slug:
            self.event_slug = slugify(self.title)
            unique_slug = self.event_slug
            num = 1
            while Event.objects.filter(event_slug=unique_slug).exists():
                unique_slug = f"{self.event_slug}-{num}"
                num += 1
            self.event_slug = unique_slug
            
        # Auto-update status based on dates AND times
        now = timezone.now()
        
        # Create datetime objects for start and end by combining date and time
        start_datetime = timezone.make_aware(
            datetime.datetime.combine(self.start_date, self.start_time)
        ) if self.start_date and self.start_time else None
        
        # For end datetime, use end_date if provided, otherwise use start_date
        end_date = self.end_date or self.start_date
        end_time = self.end_time or datetime.time(23, 59, 59)  # Default to end of day if no end_time
        end_datetime = timezone.make_aware(
            datetime.datetime.combine(end_date, end_time)
        ) if end_date and end_time else None
        
        # Update status based on datetime comparison
        if self.status not in ['cancelled', 'postponed']:
            if start_datetime and start_datetime > now:
                self.status = 'upcoming'
            elif end_datetime and end_datetime < now:
                self.status = 'completed'
            elif start_datetime and start_datetime <= now and (not end_datetime or end_datetime >= now):
                self.status = 'ongoing'
                
        # Run validation
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
    

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Citation(models.Model):
    source_name = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    description = models.TextField(blank=True, null=True)
    news = models.ForeignKey('News', related_name='citations', on_delete=models.CASCADE)

    def __str__(self):
        return self.source_name


class AttachedDocument(models.Model):
    news = models.ForeignKey('News', related_name='attached_documents', on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    file = models.FileField(upload_to='news_documents/')

    def __str__(self):
        return self.name

    @property
    def is_pdf(self):
        return self.file.name.lower().endswith('.pdf')


class News(models.Model):
    featured_image = models.ImageField(upload_to='news_images/', blank=True, null=True)
    title = models.CharField(max_length=150)
    news_slug = models.SlugField(max_length=150, unique=True, blank=True)
    content = HTMLField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='author')
    tags = models.ManyToManyField('Tag', blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_featured_image_url(self):
        return self.featured_image.url if self.featured_image else None

    def save(self, *args, **kwargs):
        if not self.news_slug:
            self.news_slug = slugify(self.title)
            unique_slug = self.news_slug
            num = 1
            while News.objects.filter(news_slug=unique_slug).exists():
                unique_slug = f"{self.news_slug}-{num}"
                num += 1
            self.news_slug = unique_slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
    

    
class Announcement(models.Model):
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('PUBLISHED', 'Published'),
        ('ARCHIVED', 'Archived'),
    )
    TARGET_CHOICES = (
        ('everyone', 'Everyone'),
        ('specific_groups', 'Specific Groups'),
    )

    title = models.CharField(max_length=100)
    content = HTMLField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    target = models.CharField(max_length=20, choices=TARGET_CHOICES, default='everyone')
    target_groups = models.ManyToManyField(Group, blank=True)
    
    def __str__(self):
        return self.title
    
class Notification(models.Model):
    STATUS_CHOICES = (
        ('UNREAD', 'Unread'),
        ('READ', 'Read'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    announcement = models.ForeignKey('Announcement', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNREAD')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f'{self.user} - {self.announcement.title}'
    

class File(models.Model):
    file = models.FileField(upload_to='files/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.file)


class Document(models.Model):
    CATEGORY_CHOICES = (
        ('internal', 'Internal'),
        ('external', 'External'),
    )
    DOCUMENT_STATUS_CHOICES = (
        ('Published', 'Published'),
        ('Draft', 'Draft'),
    )
    VISIBILITY_CHOICES = (
        ('everyone', 'Everyone'),
        ('selected_groups', 'Selected Groups'),
    )
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='uploaded_by',null=True, blank=True)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    files = models.ManyToManyField(File)
    title = models.CharField(max_length=100)
    sender = models.CharField(max_length=100)
    receiver = models.CharField(max_length=100)
    description = HTMLField(null=True, blank=True)
    date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=DOCUMENT_STATUS_CHOICES, default='Published')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='everyone')
    visible_to_groups = models.ManyToManyField(Group, blank=True)
    

    def __str__(self):
        return self.title
    
    @property
    def uploaded_by_name(self):
        """Return a human friendly name for the uploader or 'N/A' if missing."""
        user = self.uploaded_by
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
            return self.category or 'N/A'

    @property
    def status_label(self):
        """Return human readable status label."""
        try:
            return self.get_status_display()
        except Exception:
            return self.status or 'N/A'
    
class CarouselSlide(models.Model):
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='carousel_images/')
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title or f'Slide {self.id}'