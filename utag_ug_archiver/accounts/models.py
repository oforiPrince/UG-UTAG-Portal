from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from .managers import UserManager

# Create a custom user model
class School(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'School'
        verbose_name_plural = 'Schools'


class College(models.Model):
    name = models.CharField(max_length=100)
    school = models.ForeignKey('School', on_delete=models.SET_NULL, null=True, blank=True, related_name='colleges')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'College'
        verbose_name_plural = 'Colleges'


class Department(models.Model):
    name = models.CharField(max_length=100)
    college = models.ForeignKey('College', on_delete=models.SET_NULL, null=True, blank=True, related_name='departments')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'

class User(AbstractBaseUser, PermissionsMixin):
    TITLE_CHOICES = (
        ('Prof.', 'Prof.'),
        ("Prof. (Mrs.)", "Prof. (Mrs.)"),
        ('Dr.', 'Dr.'),
        ("Dr. (Alhaji)", "Dr. (Alhaji)"),
        ('Mr.', 'Mr.'),
        ('Mrs.', 'Mrs.'),
    )
    
    GENDER_CHOICES = (
        ('Male', 'Male'),
        ('Female', 'Female')
    )
    
    RANK_CHOICES = (
        ('Senior Lecturer', 'Senior Lecturer'),
        ('Lecturer', 'Lecturer'),
        ('Professor', 'Professor'),
        ('Associate Professor', 'Associate Professor'),
        ('Senior Research Fellow', 'Senior Research Fellow'),
        ('Assistant Lecturer', 'Assistant Lecturer'),
        ('Research Fellow', 'Research Fellow'),
        ('Senior Librarian', 'Senior Librarian'),
        ('Research Associate', 'Research Associate'),
        ('Dean', 'Dean'),
        ('Pro-Vice-Chancellor', 'Pro-Vice-Chancellor'),
        ('Tutor', 'Tutor'),
        ('Librarian', 'Librarian'),
        ('Director', 'Director'),
        ('Assistant Research Fellow', 'Assistant Research Fellow'),
        ('Visiting Scholar', 'Visiting Scholar'),
    )
    
    EXECUTIVE_POSITION_CHOICES = (
        ('President', 'President'),
        ('Vice President', 'Vice President'),
        ('Secretary', 'Secretary'),
        ('Treasurer', 'Treasurer'),
        ("Women's Executive Officer", "Women's Executive Officer"),
        ('Past President', 'Past President'),
        ('CBAS Rep', 'CBAS Rep'),
        ('College of Humanities Rep', 'College of Humanities Rep'),
        ('College of Health Rep', 'College of Health Rep'),
        ("College of Education Rep", "College of Education Rep"),
    )
    staff_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    title = models.CharField(max_length=15, choices=TITLE_CHOICES)
    academic_rank = models.CharField(max_length=100, blank=True, null=True)
    # first_name removed: use other_name and surname instead
    other_name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    profile_pic = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    email = models.EmailField(unique=True)
    email_sent = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    must_change_password = models.BooleanField(default=False)
    # lookup relations (can be empty for existing users)
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    college = models.ForeignKey(College, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')

    # Executive bio profile fields
    executive_summary = models.CharField(max_length=300, blank=True, null=True)
    executive_bio = models.TextField(blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    twitter_url = models.URLField(blank=True, null=True)
    personal_website_url = models.URLField(blank=True, null=True)
    created_from_dashboard = models.BooleanField(default=False)
    created_by = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True)
    is_bulk_creation = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # Executive-specific fields
    executive_image = models.ImageField(upload_to='executive_images/', blank=True, null=True)
    executive_position = models.CharField(max_length=30, choices=EXECUTIVE_POSITION_CHOICES, blank=True, null=True)
    fb_profile_url = models.URLField(blank=True, null=True)
    twitter_profile_url = models.URLField(blank=True, null=True)
    linkedin_profile_url = models.URLField(blank=True, null=True)
    date_appointed = models.DateField(null=True, blank=True)
    date_ended = models.DateField(null=True, blank=True) # 2 years after appointment
    # number of executive terms the user is currently on (1, 2, ...)
    executive_terms = models.PositiveSmallIntegerField(default=1)
    is_active_executive = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    # Use other_name and surname (no `first_name` / `last_name`)
    REQUIRED_FIELDS = ['title', 'other_name', 'surname', 'gender']
    
    def get_full_name(self):
       
        return f'{self.title} {self.surname} {self.other_name}'
    
    def get_short_name(self):
        return self.other_name
    
    def get_profile_pic_url(self):
        return self.profile_pic.url if self.profile_pic else '/static/dashboard/assets/images/users/profile.png'

    @property
    def expiry_date(self):
        """Return the expiry date: 2 years after date_appointed, or None."""
        if not self.date_appointed:
            return None
        try:
            # add 2 years conservatively
            return self.date_appointed.replace(year=self.date_appointed.year + 2)
        except Exception:
            # handle Feb 29 -> non-leap year
            from datetime import date
            return date(self.date_appointed.year + 2, self.date_appointed.month, self.date_appointed.day - 1)

    @property
    def executive_status(self):
        """Return a human-friendly executive status string.

        - If active and executive_terms == 1 => 'Current (1st Term)'
        - If active and executive_terms == 2 => 'Current (2nd Term)'
        - If active and executive_terms > 2 => 'Current (Nth Term)'
        - If not active but has executive_position or previous dates => 'Past Executive'
        """
        if self.is_active_executive:
            term = self.executive_terms or 1
            if term == 1:
                return 'Current (1st Term)'
            elif term == 2:
                return 'Current (2nd Term)'
            else:
                return f'Current ({term}th Term)'

        # not active
        if self.executive_position or self.date_appointed or self.date_ended:
            return 'Past Executive'

        return ''
    
    def get_executive_image_url(self):
        return self.executive_image.url if self.executive_image else None
    
    def is_admin(self):
        return self.groups.filter(name='Admin').exists() or self.is_superuser

    def is_executive(self):
        return self.groups.filter(name='Executive').exists()

    def is_secretary(self):
        return self.groups.filter(name='Secretary').exists()

    def is_member(self):
        return self.groups.filter(name='Member').exists()
    
    def is_acting(self):
        return self.groups.filter(name__in=['President', 'Vice President', 'Secretary', 'Treasurer', 'Past President']).exists() and self.is_active_executive and self.date_ended is None

    def __str__(self):
        return self.get_full_name()
    
    class Meta:
        permissions = [
        ('view_dashboard', 'Can view dashboard'),
        ('add_admin', 'Can add admin'),
        ('change_admin', 'Can change admin'),
        ('delete_admin', 'Can delete admin'),
        ('view_admin', 'Can view admin'),
        ('add_executive', 'Can add executive'),
        ('change_executive', 'Can change executive'),
        ('delete_executive', 'Can delete executive'),
        ('view_executive', 'Can view executive'),
        ('add_member', 'Can add member'),
        ('change_member', 'Can change member'),
        ('delete_member', 'Can delete member'),
        ('view_member', 'Can view member'),
        ]