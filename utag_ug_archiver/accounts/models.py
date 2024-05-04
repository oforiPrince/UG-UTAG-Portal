from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from .managers import UserManager

# Create a custom user model
class User(AbstractBaseUser, PermissionsMixin):
    TITLE_CHOICES = (
        ('Prof.', 'Prof.'),
        ('Dr.', 'Dr.'),
        ('Mr.', 'Mr.'),
        ('Mrs.', 'Mrs.'),
    )
    
    GENDER_CHOICES = (
        ('Male', 'Male'),
        ('Female', 'Female')
    )

    title = models.CharField(max_length=5, choices=TITLE_CHOICES)
    first_name = models.CharField(max_length=30)
    other_name = models.CharField(max_length=30, blank=True, null=True)
    last_name = models.CharField(max_length=30)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    profile_pic = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    email = models.EmailField(unique=True)
    is_admin = models.BooleanField(default=False)
    is_secretary = models.BooleanField(default=False)
    is_executive = models.BooleanField(default=False)
    is_member = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['title', 'first_name', 'last_name']
    
    def get_full_name(self):
        if self.other_name:
            return f'{self.title} {self.first_name} {self.other_name} {self.last_name}'
        else:
            return f'{self.title} {self.first_name} {self.last_name}'
    
    def get_short_name(self):
        return self.first_name
    
    def get_profile_pic_url(self):
        return self.profile_pic.url if self.profile_pic else None

    def __str__(self):
        return self.get_full_name()



