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
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

def generate_random_password():
    """Generate a secure random password of 12 characters."""
    return secrets.token_urlsafe(12)

@retry(
    stop=stop_after_attempt(5),  # Retry up to 5 times
    wait=wait_exponential(multiplier=2, max=30),  # Exponential backoff
    retry=retry_if_exception_type(SMTPException),  # Retry only on SMTP-related exceptions
)
def send_email_with_retry(email):
    """Send email with retry logic for handling temporary failures."""
    email.send()

@receiver(post_save, sender=User)
def send_credentials_email(sender, instance, created, **kwargs):
    """Send credentials email when a User is created from the dashboard."""
    if created and instance.created_from_dashboard and instance.is_bulk_creation:
        logger.info(f"Preparing to send email to {instance.email}")
        try:
            # Generate a random password
            password = generate_random_password()
            
            # Update the user's password
            instance.password = make_password(password)
            instance.save(update_fields=["password"])
            
            # Prepare the email content
            email_subject = 'Account Created'
            from_email = settings.EMAIL_HOST_USER
            email_body = render_to_string('emails/account_credentials.html', {
                'surname': instance.surname,
                'other_name': instance.other_name,
                'email': instance.email,
                'password': password
            })

            # Create the email object
            email = EmailMessage(
                email_subject,
                email_body,
                from_email,
                [instance.email]
            )
            email.content_subtype = "html"

            # Send the email with retry logic
            send_email_with_retry(email)

            # Log success
            logger.info(f"Email successfully sent to {instance.email}")

        except SMTPException as e:
            logger.error(f"SMTP error while sending email to {instance.email}: {e}")
            
            # Flag the user as email failed
            instance.email_sent = False  # Ensure the `email_sent` field exists in your model
            instance.save(update_fields=["email_sent"])
            logger.info(f"User {instance.email} flagged for email failure.")

        except Exception as e:
            logger.error(f"Unexpected error while sending email to {instance.email}: {e}")
