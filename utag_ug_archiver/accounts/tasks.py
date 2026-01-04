import logging
from celery import shared_task

from accounts.models import User
from utag_ug_archiver.utils.functions import send_credentials_email

logger = logging.getLogger(__name__)


# Email sending disabled - users now use staff_id as temporary password
# @shared_task(bind=True, max_retries=3, default_retry_delay=30)
# def send_admin_credentials(self, user_id, raw_password):
#     """Celery task wrapper to send account credentials email asynchronously.
#
#     Retries on exception up to `max_retries` with `default_retry_delay`.
#     """
#     try:
#         user = User.objects.get(pk=user_id)
#         # call the existing helper which internally handles retrying SMTP via tenacity
#         send_credentials_email(user, raw_password)
#         logger.info("Queued credentials email for user %s", user.email)
#     except User.DoesNotExist:
#         logger.error("send_admin_credentials: user %s does not exist", user_id)
#     except Exception as exc:
#         logger.exception("send_admin_credentials failed for user=%s", user_id)
#         # let Celery retry the task
#         raise self.retry(exc=exc)
