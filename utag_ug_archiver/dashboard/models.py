from django.db import models
from django.contrib.auth.models import Group
from django.utils.text import slugify
from tinymce.models import HTMLField
from accounts.models import User

class Event(models.Model):
    image = models.ImageField(upload_to='event_images/')
    title = models.CharField(max_length=100)
    event_slug = models.SlugField(max_length=100, blank=True, null=True)
    description = HTMLField()
    venue = models.CharField(max_length=100)
    date = models.DateField()
    time = models.TimeField()
    is_published = models.BooleanField(default=False)
    is_past_due = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_image_url(self):
        return self.image.url if self.image else None

    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.event_slug:
            self.event_slug = slugify(self.title)
            unique_slug = self.event_slug
            num = 1
            while Event.objects.filter(event_slug=unique_slug).exists():
                unique_slug = f"{self.event_slug}-{num}"
                num += 1
            self.event_slug = unique_slug
        super().save(*args, **kwargs)


class News(models.Model):
    featured_image = models.ImageField(upload_to='news_images/')
    title = models.CharField(max_length=150)
    news_slug = models.SlugField(max_length=150, blank=True)
    content = HTMLField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='author')
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
    
class Tag(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=50, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
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
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
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

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    announcement = models.ForeignKey('Announcement', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNREAD')
    created_at = models.DateTimeField(auto_now_add=True)
    
class ReadAnnouncement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE)
    date_read = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name} - {self.announcement.title}"
    

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
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='uploaded_by',null=True, blank=True)
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