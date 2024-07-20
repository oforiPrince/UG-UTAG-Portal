import secrets
import logging
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import User
from django.contrib.auth.hashers import make_password
from smtplib import SMTPException
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)

def generate_random_password():
    # Generate a random password of 12 characters
    return secrets.token_urlsafe(12)

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def send_email_with_retry(email):
    email.send()

@receiver(post_save, sender=User)
def send_credentials_email(sender, instance, created, **kwargs):
    if created:
        try:
            # Generate a random password
            password = generate_random_password()
            # Set the password and save the user instance
            instance.password = make_password(password)
            instance.save()
            
            # Prepare and send the email
            email_subject = 'Account Created'
            from_email = settings.EMAIL_HOST_USER
            to = instance.email
            email_body = render_to_string('emails/account_credentials.html', {
                'first_name': instance.first_name,
                'last_name': instance.last_name,
                'email': instance.email,
                'password': password
            })
            email = EmailMessage(
                email_subject,
                email_body,
                from_email,
                [to]
            )
            email.content_subtype = "html"
            send_email_with_retry(email)
        except SMTPException as e:
            logger.error(f'Error sending email to {instance.email}: {e}')
            
