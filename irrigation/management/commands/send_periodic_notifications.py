from django.core.management.base import BaseCommand
from accounts.models import CustomUser
from irrigation.models import SensorData
from irrigation.sms import SMSService
import logging
from time import sleep
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sends periodic irrigation alerts via SMS with comprehensive error handling'

    def add_arguments(self, parser):
        parser.add_argument(
            '--default-interval',
            type=int,
            default=15,
            help='Default polling interval in seconds (default: 15)'
        )
        parser.add_argument(
            '--max-retries',
            type=int,
            default=3,
            help='Max retries for failed SMS (default: 3)'
        )
        parser.add_argument(
            '--min-data-age',
            type=int,
            default=60,
            help='Minimum age of sensor data in seconds to consider for alerts (default: 60)'
        )
        parser.add_argument(
            '--check-balance',
            action='store_true',
            help='Check SMS balance before starting'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Test mode - don\'t actually send SMS'
        )

    def handle(self, *args, **options):
        retry_count = 0
        max_retries = options['max_retries']
        default_interval = options['default_interval']

        # Set test mode if dry-run is enabled
        if options['dry_run']:
            from django.conf import settings
            settings.EGOSMS_CONFIG['TEST_MODE'] = True
            logger.info("DRY RUN MODE: No actual SMS will be sent")

        # Check balance if requested
        if options['check_balance']:
            self._check_sms_balance()

        logger.info(f"Starting SMS notification service with default {default_interval}s interval")

        while True:
            try:
                # Get users who want notifications
                users_with_notifications = CustomUser.objects.filter(
                    is_active=True,
                    phone_number__isnull=False,
                    receive_sms_alerts=True
                ).exclude(phone_number='')

                if users_with_notifications.exists():
                    # Calculate the minimum interval needed
                    min_interval = min(
                        user.sms_notification_frequency
                        for user in users_with_notifications
                    )
                    logger.info(
                        f"Found {users_with_notifications.count()} users with SMS enabled. Minimum interval: {min_interval}s")
                else:
                    min_interval = default_interval
                    logger.info(f"No users with SMS enabled. Using default interval: {min_interval}s")

                # Send notifications
                success_count, failure_count = self._send_notifications(options['min_data_age'])

                if success_count > 0:
                    logger.info(f"Sent {success_count} SMS notifications successfully")
                elif failure_count > 0:
                    logger.warning(f"Failed to send {failure_count} SMS notifications")
                else:
                    logger.info("No notifications sent in this cycle")

                # Sleep for the calculated interval
                logger.info(f"Sleeping for {min_interval} seconds...")
                sleep(min_interval)

            except ObjectDoesNotExist:
                logger.warning("No sensor data available - retrying in 60s")
                sleep(60)
            except Exception as e:
                retry_count += 1
                logger.error(f"Error occurred (retry {retry_count}/{max_retries}): {str(e)}")

                if retry_count >= max_retries:
                    logger.error(f"Max retries ({max_retries}) exceeded. Exiting.")
                    break

                sleep_duration = min(300, 60 * retry_count)
                sleep(sleep_duration)

    def _check_sms_balance(self):
        """Check SMS balance before starting"""
        try:
            success, message = SMSService.check_balance()
            if success:
                logger.info(f"SMS Balance: {message}")
            else:
                logger.warning(f"Failed to check balance: {message}")
        except Exception as e:
            logger.error(f"Error checking SMS balance: {str(e)}")

    def _send_notifications(self, min_data_age):
        """Send notifications to eligible users"""
        try:
            # Get latest sensor data that's at least min_data_age seconds old
            time_threshold = timezone.now() - timedelta(seconds=min_data_age)
            latest_data = SensorData.objects.filter(
                timestamp__lte=time_threshold
            ).latest('timestamp')
            logger.info(f"Using sensor data from {latest_data.timestamp}")

        except ObjectDoesNotExist:
            logger.warning("No valid sensor data available in database")
            return 0, 0

        # Get eligible users who want notifications
        users = CustomUser.objects.filter(
            is_active=True,
            phone_number__isnull=False,
            receive_sms_alerts=True
        ).exclude(phone_number='')

        if not users.exists():
            logger.info("No active users with SMS notifications enabled")
            return 0, 0

        success_count = 0
        failure_count = 0

        for user in users:
            # Check if it's time to send notification based on user's frequency
            if self._should_send_notification(user):
                logger.info(f"Sending SMS to {user.username} (phone: {user.phone_number})")
                success, message = SMSService.send_alert(user, latest_data)
                if success:
                    logger.info(f"Successfully sent to {user.phone_number}")
                    success_count += 1
                    # Update last notification time
                    user.last_notification_sent = timezone.now()
                    user.save(update_fields=['last_notification_sent'])
                else:
                    if "not eligible" not in message.lower():
                        logger.warning(f"Not sent to {user.phone_number}: {message}")
                    failure_count += 1
            else:
                time_since_last = timezone.now() - user.last_notification_sent
                logger.debug(
                    f"Not time yet for {user.username}. Last sent: {time_since_last.total_seconds():.0f}s ago, Frequency: {user.sms_notification_frequency}s")

        return success_count, failure_count

    def _should_send_notification(self, user):
        """Check if it's time to send notification based on user's frequency"""
        if not user.last_notification_sent:
            return True

        time_since_last = timezone.now() - user.last_notification_sent
        return time_since_last.total_seconds() >= user.sms_notification_frequency
