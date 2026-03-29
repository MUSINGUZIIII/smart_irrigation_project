import pytz
import requests
from urllib.parse import quote
from django.conf import settings
import logging
from django.utils import timezone
from .models import WaterUsage, WaterTankLevel  # Add this import

logger = logging.getLogger(__name__)


class SMSServiceError(Exception):
    def __init__(self, message, phone_number=None, details=None):
        self.phone_number = phone_number
        self.details = details
        super().__init__(f"SMS Error: {message}")


class SMSService:
    @staticmethod
    def clean_phone_number(phone):
        """Clean and validate phone number"""
        if not phone:
            return None

        try:
            # Remove any non-digit characters except +
            cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')

            # Ensure it starts with country code
            if cleaned.startswith('+256'):
                return cleaned[1:]  # Remove + for EgoSMS
            elif cleaned.startswith('256'):
                return cleaned
            elif cleaned.startswith('0'):
                return '256' + cleaned[1:]  # Convert 07... to 2567...
            else:
                return None

        except Exception:
            return None

    @classmethod
    def send_alert(cls, user, sensor_data):
        """Send irrigation alert with water usage info"""
        if not user or not user.phone_number:
            return False, "Invalid user or missing phone number"

        # Double-check that user wants notifications
        if not user.receive_sms_alerts:
            return False, "User has disabled SMS notifications"

        try:
            # Get water usage data for the last 24 hours
            water_usage_data = cls._get_water_usage_summary(user)

            # Get current tank level
            tank_level = cls._get_current_tank_level(user)

            # Build message with water usage info
            message = cls._build_alert_message(sensor_data, user, water_usage_data, tank_level)

            success, result_message = cls._send_sms(user.phone_number, message)

            return success, result_message

        except Exception as e:
            logger.error(f"Error for {user.username}: {str(e)}")
            return False, "Failed to send alert"

    @classmethod
    def _get_water_usage_summary(cls, user):
        """Get water usage summary for the last 24 hours and last 7 days"""
        try:
            now = timezone.now()
            last_24h = now - timezone.timedelta(hours=24)
            last_7d = now - timezone.timedelta(days=7)

            # Get usage for last 24 hours
            recent_usage = WaterUsage.objects.filter(
                user=user,
                timestamp__gte=last_24h
            )
            total_24h = sum(usage.volume_used for usage in recent_usage)

            # Get usage for last 7 days
            weekly_usage = WaterUsage.objects.filter(
                user=user,
                timestamp__gte=last_7d
            )
            total_7d = sum(usage.volume_used for usage in weekly_usage)

            # Get latest usage record
            latest_usage = WaterUsage.objects.filter(user=user).order_by('-timestamp').first()

            return {
                'last_24h': round(total_24h, 1),
                'last_7d': round(total_7d, 1),
                'latest': latest_usage,
                'has_data': latest_usage is not None
            }
        except Exception as e:
            logger.error(f"Error getting water usage: {e}")
            return {
                'last_24h': 0,
                'last_7d': 0,
                'latest': None,
                'has_data': False
            }

    @classmethod
    def _get_current_tank_level(cls, user):
        """Get current tank level"""
        try:
            latest_level = WaterTankLevel.objects.filter(user=user).order_by('-timestamp').first()

            if latest_level:
                return {
                    'percentage': latest_level.level_percentage,
                    'volume': latest_level.volume,
                    'status': cls._get_tank_status(latest_level.level_percentage)
                }
            return None
        except Exception as e:
            logger.error(f"Error getting tank level: {e}")
            return None

    @staticmethod
    def _get_tank_status(percentage):
        """Get tank status based on percentage"""
        if percentage < 10:
            return "CRITICAL"
        elif percentage < 20:
            return "LOW"
        elif percentage < 50:
            return "MODERATE"
        else:
            return "GOOD"

    @classmethod
    def _build_alert_message(cls, sensor_data, user, water_usage_data, tank_level):
        """Construct the alert message with connection status, EAT time, and water usage"""
        # Get values with proper None handling
        threshold = getattr(user, 'sms_alert_threshold', None)
        if threshold is None:
            threshold = getattr(sensor_data, 'threshold', 'N/A')

        moisture = getattr(sensor_data, 'moisture', 'N/A')
        temperature = getattr(sensor_data, 'temperature', 'N/A')
        humidity = getattr(sensor_data, 'humidity', 'N/A')
        pump_status = getattr(sensor_data, 'pump_status', False)

        # Handle None values for comparison
        if moisture is not None and threshold is not None and isinstance(moisture, (int, float)) and isinstance(
                threshold, (int, float)):
            irrigation_status = "ACTIVE" if moisture < threshold else "IDLE"
        else:
            irrigation_status = "UNKNOWN"

        # Convert timestamp to East African Time (EAT)
        eat_timezone = pytz.timezone('Africa/Nairobi')
        sensor_timestamp = getattr(sensor_data, 'timestamp', timezone.now())
        eat_time = sensor_timestamp.astimezone(eat_timezone)

        # Check connection status (online/offline)
        time_diff = timezone.now() - sensor_timestamp
        if time_diff.total_seconds() <= 300:  # 5 minutes threshold for online status
            connection_status = "ONLINE"
        else:
            connection_status = "OFFLINE"

        # Build message parts
        message_parts = [
            f"SMART IRRIGATION UPDATE",
            f"━━━━━━━━━━━━━━━━",
            f"Hello {user.username}!",
            f"Status: {connection_status}",
            f"Time: {eat_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"━━━━━━━━━━━━━━━━",
            f"SOIL CONDITIONS:",
            f"• Moisture: {moisture if moisture is not None else 'N/A'}%",
            f"• Threshold: {threshold if threshold is not None else 'N/A'}%",
            f"• Irrigation: {irrigation_status}",
            f"• Pump: {'ON 🔵' if pump_status else 'OFF ⚪'}",
            f"• Temp: {temperature if temperature is not None else 'N/A'}°C",
            f"• Humidity: {humidity if humidity is not None else 'N/A'}%",
        ]

        # Add water tank information
        if tank_level:
            message_parts.extend([
                f"━━━━━━━━━━━━━━━━",
                f" WATER TANK:",
                f"• Level: {tank_level['percentage']:.1f}%",
                f"• Volume: {tank_level['volume']:.1f}L",
                f"• Status: {tank_level['status']}"
            ])

        # Add water usage information
        if water_usage_data['has_data']:
            latest = water_usage_data['latest']
            message_parts.extend([
                f"━━━━━━━━━━━━━━━━",
                f"📊 WATER USAGE:",
                f"• Last 24h: {water_usage_data['last_24h']}L",
                f"• Last 7 days: {water_usage_data['last_7d']}L",
            ])

            if latest:
                # Format the period nicely
                hours = latest.measurement_period.total_seconds() / 3600
                message_parts.append(
                    f"• Latest: {latest.volume_used:.1f}L in {hours:.1f}h"
                )
        else:
            message_parts.extend([
                f"━━━━━━━━━━━━━━━━",
                f" WATER USAGE:",
                f"• No usage data yet"
            ])

        message_parts.extend([
            f"━━━━━━━━━━━━━━━━",
            f" Track live at:",
            f"smart-irrigation.app",
            f"━━━━━━━━━━━━━━━━"
        ])

        return "\n".join(message_parts)

    @classmethod
    def send_water_usage_report(cls, user, period_days=7):
        """Send a detailed water usage report via SMS"""
        if not user or not user.phone_number or not user.receive_sms_alerts:
            return False, "Cannot send SMS"

        try:
            # Get water usage data
            end_date = timezone.now()
            start_date = end_date - timezone.timedelta(days=period_days)

            usage_records = WaterUsage.objects.filter(
                user=user,
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('-timestamp')

            if not usage_records:
                message = f"📊 WATER USAGE REPORT\nNo water usage data available for the last {period_days} days."
            else:
                # Calculate statistics
                total_usage = sum(record.volume_used for record in usage_records)
                avg_daily = total_usage / period_days
                max_usage = max(record.volume_used for record in usage_records) if usage_records else 0

                # Get current tank level
                tank_level = cls._get_current_tank_level(user)

                message_parts = [
                    f"📊 WATER USAGE REPORT",
                    f"━━━━━━━━━━━━━━━━",
                    f"Hello {user.username}!",
                    f"Period: Last {period_days} days",
                    f"━━━━━━━━━━━━━━━━",
                    f"📈 SUMMARY:",
                    f"• Total used: {total_usage:.1f}L",
                    f"• Daily avg: {avg_daily:.1f}L",
                    f"• Max usage: {max_usage:.1f}L",
                    f"• Records: {len(usage_records)}",
                ]

                if tank_level:
                    message_parts.extend([
                        f"━━━━━━━━━━━━━━━━",
                        f"💧 CURRENT TANK:",
                        f"• Level: {tank_level['percentage']:.1f}%",
                        f"• Volume: {tank_level['volume']:.1f}L",
                        f"• Status: {tank_level['status']}"
                    ])

                # Add top 3 usage events
                top_events = usage_records[:3]
                if top_events:
                    message_parts.append(f"━━━━━━━━━━━━━━━━")
                    message_parts.append(f"📋 TOP USAGE EVENTS:")
                    for i, event in enumerate(top_events, 1):
                        hours = event.measurement_period.total_seconds() / 3600
                        date = event.timestamp.astimezone(pytz.timezone('Africa/Nairobi')).strftime('%b %d')
                        message_parts.append(
                            f"{i}. {date}: {event.volume_used:.1f}L ({hours:.1f}h)"
                        )

                message_parts.append(f"━━━━━━━━━━━━━━━━")

            success, result_message = cls._send_sms(user.phone_number, "\n".join(message_parts))
            return success, result_message

        except Exception as e:
            logger.error(f"Error sending water usage report: {e}")
            return False, str(e)

    @classmethod
    def _send_sms(cls, phone, message):
        """Core SMS sending logic"""
        if settings.EGOSMS_CONFIG.get('TEST_MODE', True):
            logger.info(f"TEST MODE: SMS to {phone}: {message[:50]}...")
            return True, "Test mode - no SMS sent"

        clean_num = cls.clean_phone_number(phone)
        if not clean_num:
            return False, "Invalid phone number format"

        try:
            params = {
                'username': settings.EGOSMS_CONFIG['USERNAME'],
                'password': settings.EGOSMS_CONFIG['PASSWORD'],
                'number': clean_num,
                'message': quote(message),
                'sender': settings.EGOSMS_CONFIG['SENDER_ID'],
                'priority': 0
            }

            query_string = '&'.join(f"{k}={v}" for k, v in params.items())
            url = f"{settings.EGOSMS_CONFIG['API_URL']}?{query_string}"

            print(f"DEBUG: Sending SMS to EgoSMS URL: {url}")
            response = requests.get(url, timeout=15)
            response_text = response.text.strip()

            print(f"DEBUG: EgoSMS response: '{response_text}'")
            print(f"DEBUG: Response status code: {response.status_code}")

            # EgoSMS returns "OK" for success, anything else is failure
            if response_text.upper() == "OK":
                logger.info(f"SMS successfully sent to {phone}")
                return True, "SMS sent successfully"
            else:
                logger.error(f"EgoSMS error: {response_text}")
                return False, f"EgoSMS error: {response_text}"

        except Exception as e:
            logger.error(f"Network error: {str(e)}")
            return False, f"Network error: {str(e)}"

    @classmethod
    def check_balance(cls):
        """Check EgoSMS account balance"""
        if settings.EGOSMS_CONFIG.get('TEST_MODE', True):
            return True, "Test mode - balance check skipped"

        try:
            params = {
                'username': settings.EGOSMS_CONFIG['USERNAME'],
                'password': settings.EGOSMS_CONFIG['PASSWORD'],
                'action': 'balance'
            }

            query_string = '&'.join(f"{k}={v}" for k, v in params.items())
            url = f"{settings.EGOSMS_CONFIG['API_URL']}?{query_string}"

            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                balance_text = response.text.strip()
                return True, f"Balance: {balance_text} credits"
            else:
                return False, f"HTTP error: {response.status_code}"

        except Exception as e:
            return False, f"Error: {str(e)}"

    @classmethod
    def send_direct_sms(cls, phone_number, message):
        """Direct SMS sending"""
        if settings.EGOSMS_CONFIG.get('TEST_MODE', True):
            logger.info(f"TEST MODE: Direct SMS to {phone_number}: {message[:50]}...")
            return True, "Test mode - no SMS sent"

        clean_num = cls.clean_phone_number(phone_number)
        if not clean_num:
            return False, "Invalid phone number format"

        try:
            params = {
                'username': settings.EGOSMS_CONFIG['USERNAME'],
                'password': settings.EGOSMS_CONFIG['PASSWORD'],
                'number': clean_num,
                'message': quote(message),
                'sender': settings.EGOSMS_CONFIG['SENDER_ID'],
                'priority': 0
            }

            query_string = '&'.join(f"{k}={v}" for k, v in params.items())
            url = f"{settings.EGOSMS_CONFIG['API_URL']}?{query_string}"

            response = requests.get(url, timeout=15)

            if response.text.strip() == "OK":
                logger.info(f"Direct SMS successfully sent to {phone_number}")
                return True, "SMS sent successfully"
            else:
                return False, f"EgoSMS error: {response.text}"

        except Exception as e:
            return False, f"Network error: {str(e)}"


# Required function for compatibility
def send_irrigation_alert(user, sensor_data):
    """Legacy interface maintained for compatibility"""
    return SMSService.send_alert(user, sensor_data)


# New function to send water usage reports
def send_water_usage_report(user, period_days=7):
    """Send water usage report via SMS"""
    return SMSService.send_water_usage_report(user, period_days)


def send_stock_alert(user, alert):
    """Send urgent stock alert via SMS"""
    if not user or not user.phone_number or not user.receive_sms_alerts:
        return False, "Cannot send SMS"

    try:
        message = (
            f"🚨 URGENT: WATER STOCK ALERT\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Hello {user.username},\n\n"
            f"Your irrigation system needs attention!\n\n"
            f"📊 Current Status:\n"
            f"• Tank Level: {alert.current_tank_level:.1f}L ({alert.current_tank_level_percentage:.1f}%)\n"
            f"• Days Remaining: {alert.estimated_days_remaining:.1f} days\n"
            f"• Irrigations Left: {alert.estimated_irrigations_remaining}\n\n"
            f"⚠️ Based on your irrigation frequency, you need to stock water "
            f"within the next 2-3 days to avoid interruption.\n\n"
            f"💧 Recommended to stock {alert.recommended_stock_amount:.0f}L by "
            f"{alert.recommended_stock_date.strftime('%d %b')}\n\n"
            f"Track usage at: smart-irrigation.app/water-usage"
        )

        return SMSService._send_sms(user.phone_number, message)

    except Exception as e:
        logger.error(f"Error sending stock alert: {e}")
        return False, str(e)

