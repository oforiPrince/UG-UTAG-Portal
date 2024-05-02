from django.db import models
from django.conf import settings

from accounts.models import User

class Event(models.Model):
    image = models.ImageField(upload_to='event_images/')
    title = models.CharField(max_length=100)
    description = models.TextField()
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


class News(models.Model):
    featured_image = models.ImageField(upload_to='news_images/')
    title = models.CharField(max_length=100)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='author')
    tags = models.CharField(max_length=100, blank=True, null=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_featured_image_url(self):
        return self.featured_image.url if self.featured_image else None

    def __str__(self):
        return self.title
    
class Announcement(models.Model):
    TARGET_GROUP_CHOICES = (
        ('ALL', 'All'),
        ('MEMBERS', 'Members'),
        ('EXECUTIVES', 'Executives'),
    )
    title = models.CharField(max_length=100)
    content = models.TextField()
    target_group = models.CharField(max_length=20, choices=TARGET_GROUP_CHOICES, default='ALL')
    is_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title


class ExecutivePosition(models.Model):
    LEADERSHIP_NAME_CHOICES = (
        ('President', 'President'),
        ('Vice President', 'Vice President'),
        ('Secretary', 'Secretary'),
        ('Treasurer', 'Treasurer'),
        ('Committee Member', 'Committee Member'),
    )
    name = models.CharField(max_length=30, choices=LEADERSHIP_NAME_CHOICES, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Executive(models.Model):
    image = models.ImageField(upload_to='executive_images/', blank=True, null=True)
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name='member')
    position = models.ForeignKey(ExecutivePosition, on_delete=models.CASCADE)
    fb_username = models.CharField(max_length=100, blank=True, null=True)
    twitter_username = models.CharField(max_length=100, blank=True, null=True)
    linkedin_username = models.CharField(max_length=100, blank=True, null=True)
    is_executive_officer = models.BooleanField(default=False)
    date_appointed = models.DateField()
    date_ended = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.member.first_name} - {self.position.name}"
    

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
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('archived', 'Archived'),
        ('draft', 'Draft'),
    )
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='uploaded_by',null=True, blank=True)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    files = models.ManyToManyField(File)
    title = models.CharField(max_length=100)
    sender = models.CharField(max_length=100)
    receiver = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=DOCUMENT_STATUS_CHOICES, default='approved')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

    def __str__(self):
        return self.title
    
