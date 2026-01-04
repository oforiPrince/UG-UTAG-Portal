from django.contrib import admin
from django import forms

admin.site.site_header = "UTAG-UG Archiver Admin"
admin.site.site_title = "UTAG-UG Archiver Admin Portal"
admin.site.index_title = "Welcome to UTAG-UG Archiver Portal"

from django.contrib import admin
from django import forms
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField

admin.site.site_header = "UTAG-UG Archiver Admin"
admin.site.site_title = "UTAG-UG Archiver Admin Portal"
admin.site.index_title = "Welcome to UTAG-UG Archiver Portal"

from .models import User


class UserCreationForm(forms.ModelForm):
	"""A form for creating new users. Includes all the required
	fields, plus a repeated password."""
	password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
	password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput)

	class Meta:
		model = User
		fields = ('email', 'title', 'other_name', 'surname', 'gender')

	def clean_password2(self):
		# Check that the two password entries match
		password1 = self.cleaned_data.get('password1')
		password2 = self.cleaned_data.get('password2')
		if password1 and password2 and password1 != password2:
			raise forms.ValidationError("Passwords don't match")
		return password2

	def save(self, commit=True):
		# Save the provided password in hashed format
		user = super().save(commit=False)
		user.set_password(self.cleaned_data['password1'])
		if commit:
			user.save()
		return user


class UserChangeForm(forms.ModelForm):
	"""A form for updating users. Includes all the fields on
	the user, but replaces the password field with admin's
	password hash display field.
	"""
	password = ReadOnlyPasswordHashField()

	class Meta:
		model = User
		fields = '__all__'

	def clean_password(self):
		# Regardless of what the user provides, return the initial value.
		# This is done here, so that the password hash is not overwritten
		# unless explicitly changed via a dedicated change password form.
		return self.initial.get('password')


class UserAdmin(BaseUserAdmin):
	# The forms to add and change user instances
	form = UserChangeForm
	add_form = UserCreationForm

	list_display = ('email', 'surname', 'other_name', 'is_staff', 'is_superuser')
	list_filter = ('is_staff', 'is_superuser')
	search_fields = ('email', 'surname', 'other_name')
	ordering = ('email',)
	filter_horizontal = ()

	fieldsets = (
		(None, {'fields': ('email', 'password')}),
		('Personal info', {'fields': ('title', 'other_name', 'surname', 'gender', 'phone_number', 'profile_pic')}),
		('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
		('Important dates', {'fields': ('last_login', 'created_at')}),
	)

	# add_fieldsets is used when creating a user via the admin
	add_fieldsets = (
		(None, {
			'classes': ('wide',),
			'fields': ('email', 'title', 'other_name', 'surname', 'gender', 'password1', 'password2'),
		}),
	)


admin.site.register(User, UserAdmin)
