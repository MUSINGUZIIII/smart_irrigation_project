from celery import shared_task
from django.utils import timezone
from accounts.models import CustomUser
from irrigation.models import SensorData
from irrigation.sms import SMSService
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_periodic_sms_alerts():
    """Celery task to send periodic SMS alerts"""
    try:
        # Get latest sensor data
        latest_data = SensorData.objects.latest('timestamp')
        logger.info(f"Processing SMS alerts with data from {latest_data.timestamp}")

        # Get users who want notifications
        users = CustomUser.objects.filter(
            is_active=True,
            phone_number__isnull=False,
            receive_sms_alerts=True
        ).exclude(phone_number='')

        success_count = 0
        failure_count = 0

        for user in users:
            # Check if it's time to send notification
            if should_send_notification(user):
                success, message = SMSService.send_alert(user, latest_data)
                if success:
                    logger.info(f"SMS sent to {user.phone_number}")
                    success_count += 1
                    # Update last notification time
                    user.last_notification_sent = timezone.now()
                    user.save(update_fields=['last_notification_sent'])
                else:
                    logger.warning(f"Failed to send to {user.phone_number}: {message}")
                    failure_count += 1

        return f"Success: {success_count}, Failed: {failure_count}"

    except Exception as e:
        logger.error(f"Error in SMS task: {str(e)}")
        return f"Error: {str(e)}"


def should_send_notification(user):
    """Check if it's time to send notification"""
    if not user.last_notification_sent:
        return True

    time_since_last = timezone.now() - user.last_notification_sent
    return time_since_last.total_seconds() >= user.sms_notification_frequency
