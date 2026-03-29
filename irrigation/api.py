import logging
import pytz
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta, datetime
from .models import SensorData, ControlCommand, Threshold, SystemConfiguration, DeviceStatus, Schedule, UserPreference, \
    WaterTankLevel, WaterUsage
from django.contrib.auth import get_user_model
from .sms import send_irrigation_alert
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from datetime import timedelta, datetime
from .models import IrrigationEvent, IrrigationFrequencyAnalysis, WaterStockAlert
from collections import defaultdict

logger = logging.getLogger(__name__)
User = get_user_model()

# Constants
DEFAULT_THRESHOLD = 30
MANUAL_MODE_DURATION = timedelta(hours=1)

# Set to East Africa Time (EAT)
EAT = pytz.timezone('Africa/Nairobi')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def receive_sensor_data(request):
    logger.info(f"[API] Incoming sensor data from {request.META.get('REMOTE_ADDR')}")
    logger.debug(f"[DATA] {request.data}")

    if request.method == 'POST':
        try:
            data = request.data
            user = request.user
            logger.info(f"[USER] Processing data for {user.username}")

            # Convert 'NA' strings to None
            def clean_value(val):
                if val in ('NA', None, '', 'null'):
                    return None
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return None

            # Save sensor data
            sensor_data = SensorData.objects.create(
                moisture=clean_value(data.get('moisture')),
                pump_status=data.get('pump_status', False),
                threshold=data.get('threshold', DEFAULT_THRESHOLD),
                user=user
            )

            # Update cache
            cache_keys = {
                f'moisture_{user.id}': sensor_data.moisture,
                f'pump_state_{user.id}': 'on' if sensor_data.pump_status else 'off',
                f'threshold_{user.id}': sensor_data.threshold
            }

            for key, value in cache_keys.items():
                cache.set(key, value, timeout=None)

            # Send WebSocket update
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"sensor_updates_{user.id}",
                    {
                        "type": "send_sensor_data",
                        "data": {
                            "moisture": sensor_data.moisture,
                            "pump_status": sensor_data.pump_status,
                            "timestamp": sensor_data.timestamp.isoformat()
                        }
                    }
                )
                logger.debug("[WEBSOCKET] Update sent")
            except Exception as ws_error:
                logger.error(f"[WEBSOCKET] Error: {ws_error}")

            # Send alerts if needed
            send_irrigation_alert(user, sensor_data)

            logger.info("[API] Data processed successfully")
            return Response({"status": "success"}, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"[ERROR] Type: {type(e)}, Message: {str(e)}", exc_info=True)
            return Response({
                "status": "error",
                "message": str(e),
                "type": type(e).__name__
            }, status=status.HTTP_400_BAD_REQUEST)
    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def control_system(request):
    logger.info(f"[CONTROL] Request from {request.META.get('REMOTE_ADDR')}")
    logger.debug(f"[CONTROL DATA] {request.data}")

    try:
        action = request.data.get('action')
        user = request.user
        user_id = user.id

        # Helper function to create control command
        def create_control_command(pump=None, manual=None, emergency=None):
            return ControlCommand.objects.create(
                pump_status=pump if pump is not None else False,
                manual_mode=manual if manual is not None else False,
                emergency=emergency if emergency is not None else False,
                user=user
            )

        if action == 'toggle_pump':
            # Only allow pump toggle in manual mode
            if not cache.get(f'system_mode_{user_id}', False):
                logger.warning("[PUMP] Attempted toggle while not in manual mode")
                return Response(
                    {"error": "System must be in manual mode to control pump"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Verify the requested state is different from current state
            current_pump_state = cache.get(f'pump_state_{user_id}', 'off')
            requested_state = request.data.get('state', False)
            requested_state_str = 'on' if requested_state else 'off'

            if current_pump_state == requested_state_str:
                logger.warning(f"[PUMP] Already in requested state: {requested_state_str}")
                return Response({"pump": current_pump_state})

            # Only proceed if state is actually changing
            cache.set(f'pump_state_{user_id}', requested_state_str, timeout=None)
            create_control_command(pump=requested_state)
            logger.info(f"[PUMP] State changed to {requested_state_str}")
            return Response({"pump": requested_state_str})

        elif action == 'set_threshold':
            threshold = request.data.get('threshold')
            if threshold is None:
                logger.warning("[THRESHOLD] No value provided")
                return Response({"error": "Threshold value required"}, status=400)

            try:
                threshold = int(threshold)
                if not (0 <= threshold <= 100):
                    raise ValueError("Threshold must be between 0 and 100")
            except ValueError as e:
                logger.error(f"[THRESHOLD] Invalid value: {threshold}")
                return Response({"error": str(e)}, status=400)

            Threshold.objects.create(threshold=threshold, user=user)
            cache.set(f'threshold_{user_id}', threshold, timeout=None)
            logger.info(f"[THRESHOLD] Set to {threshold}%")
            return Response({"threshold": threshold})

        elif action == 'set_mode':
            manual_mode = request.data.get('manual_mode', False)
            cache.set(f'system_mode_{user_id}', manual_mode, timeout=None)
            # Get current states from cache
            pump_state = cache.get(f'pump_state_{user_id}', 'off') == 'on'
            emergency_state = cache.get(f'emergency_{user_id}', False)
            # When switching to auto mode, ensure pump is off
            if not manual_mode:
                pump_state = False
                cache.set(f'pump_state_{user_id}', 'off', timeout=None)
                logger.info("[MODE] Switched to auto mode - ensuring pump is off")
            # Create control command with all required fields
            ControlCommand.objects.create(
                pump_status=pump_state,
                manual_mode=manual_mode,
                emergency=emergency_state,
                user=user
            )
            logger.info(f"[MODE] Changed to {'manual' if manual_mode else 'auto'}")
            return Response({
                "manual_mode": manual_mode,
                "pump": "off" if not manual_mode else ("on" if pump_state else "off")
            })

        elif action == 'emergency_stop':
            cache.set(f'emergency_{user_id}', True, timeout=None)
            config = SystemConfiguration.get_for_user(user)
            config.emergency_stop = True
            config.save()
            cache.set(f'pump_state_{user_id}', 'off', timeout=None)

            # Create control command with all required fields
            ControlCommand.objects.create(
                emergency=True,
                pump_status=False,
                manual_mode=False,
                user=user
            )

            logger.warning("[EMERGENCY] Stop activated")
            return Response({
                "emergency": True,
                "pump": "off"
            })

        elif action == 'reset_emergency':
            current_emergency = cache.get(f'emergency_{user_id}', False)
            cache.set(f'emergency_{user_id}', False, timeout=None)
            config = SystemConfiguration.get_for_user(user)
            config.emergency_stop = False
            config.save()
            if not current_emergency:
                logger.warning("[EMERGENCY] No active emergency to reset")
                return Response({
                    "status": "no_active_emergency",
                    "emergency": False,
                    "system_active": cache.get(f'system_active_{user_id}', False),
                    "pump": cache.get(f'pump_state_{user_id}', 'off')
                })
            cache.set(f'emergency_{user_id}', False, timeout=None)
            # Convert string states to boolean for database
            pump_state = cache.get(f'pump_state_{user_id}', 'off') == 'on'
            manual_mode = cache.get(f'system_mode_{user_id}', False)
            ControlCommand.objects.create(
                emergency=False,
                pump_status=pump_state,
                manual_mode=manual_mode,
                user=user
            )

            logger.info("[EMERGENCY] Reset")
            return Response({
                "status": "emergency_reset",
                "emergency": False,
                "system_active": cache.get(f'system_active_{user_id}', False),
                "pump": cache.get(f'pump_state_{user_id}', 'off')
            })

        elif action == 'disconnect':
            # Clear connection status
            cache.set(f'device_connection_{user_id}', False, timeout=None)
            logger.info("[CONNECTION] Manually disconnected by user")
            return Response({
                "status": "disconnected",
                "connected": False
            })

        elif action == 'get_state':
            # Get current state from cache with safe defaults
            response_data = {
                "pump": cache.get(f'pump_state_{user_id}', 'off'),
                "manual_mode": cache.get(f'system_mode_{user_id}', False),
                "emergency": cache.get(f'emergency_{user_id}', False),
                "threshold": cache.get(f'threshold_{user_id}', DEFAULT_THRESHOLD),
                "irrigation_active": False,
                "connected": cache.get(f'device_connection_{user_id}', False),
                "last_seen": cache.get(f'device_last_seen_{user_id}'),
            }

            # Only allow irrigation when in manual mode and not in emergency
            if response_data['manual_mode'] and not response_data['emergency']:
                response_data['irrigation_active'] = response_data['pump'] == 'on'

            # Get next scheduled irrigation if exists
            next_schedule = Schedule.objects.filter(
                user=user,
                is_active=True,
                scheduled_time__gte=timezone.now()
            ).order_by('scheduled_time').first()

            if next_schedule:
                response_data["schedule"] = {
                    "year": next_schedule.scheduled_time.year,
                    "date": next_schedule.scheduled_time.date().isoformat(),
                    "time": next_schedule.scheduled_time.time().isoformat(),
                    "duration": next_schedule.duration
                }

            # Get latest sensor data
            latest_data = SensorData.objects.filter(user=user).order_by('-timestamp').first()
            if latest_data:
                response_data.update({
                    "timestamp": latest_data.timestamp.isoformat()
                })
            else:
                response_data.update({
                    "timestamp": timezone.now().isoformat()
                })

            logger.debug("[STATE] Current state sent")
            return Response(response_data)

        logger.warning(f"[CONTROL] Invalid action: {action}")
        return Response({"error": "Invalid action"}, status=400)

    except Exception as e:
        logger.error(f"[CONTROL ERROR] {str(e)}", exc_info=True)
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_system_status(request):
    """
    Fetch current system status including sensor readings.
    """
    try:
        user = request.user
        user_id = user.id
        latest_data = SensorData.objects.filter(user=user).order_by('-timestamp').first()

        def format_value(value):
            return value if value is not None else 'NA'

        return Response({
            "pump": cache.get(f'pump_state_{user_id}', 'off'),
            "moisture": format_value(latest_data.moisture if latest_data else None),
            "threshold": cache.get(f'threshold_{user_id}', DEFAULT_THRESHOLD),
            "system_mode": cache.get(f'system_mode_{user_id}', False),
            "emergency": cache.get(f'emergency_{user_id}', False),
            "timestamp": latest_data.timestamp.isoformat() if latest_data else timezone.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Status error: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_configuration(request):
    """Save system configuration (crop type, soil type, threshold)."""
    try:
        user = request.user
        crop = request.data.get('crop')
        soil = request.data.get('soil')
        threshold = request.data.get('threshold')

        # Get or create user preferences
        preferences, created = UserPreference.objects.get_or_create(user=user)

        # Update fields if provided
        if crop is not None:
            preferences.crop_type = crop
        if soil is not None:
            preferences.soil_type = soil
        if threshold is not None:
            preferences.soil_moisture_threshold = threshold

        preferences.save()

        # Update cache
        cache.set(f'crop_{user.id}', preferences.crop_type, timeout=None)
        cache.set(f'soil_{user.id}', preferences.soil_type, timeout=None)
        cache.set(f'threshold_{user.id}', preferences.soil_moisture_threshold, timeout=None)

        return Response({
            "status": "success",
            "crop": preferences.crop_type,
            "soil": preferences.soil_type,
            "threshold": preferences.soil_moisture_threshold,
            "recommended_threshold": preferences.recommended_threshold,
            "threshold_suggestion": preferences.get_threshold_suggestion()
        })

    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_configuration(request):
    """Get current system configuration."""
    try:
        user = request.user
        preferences = UserPreference.objects.filter(user=user).first()

        if not preferences:
            return Response({
                "crop": None,
                "soil": None,
                "threshold": DEFAULT_THRESHOLD,
                "recommended_threshold": DEFAULT_THRESHOLD,
                "threshold_suggestion": "Please configure your crop and soil type"
            })

        return Response({
            "crop": preferences.crop_type,
            "soil": preferences.soil_type,
            "threshold": preferences.soil_moisture_threshold,
            "recommended_threshold": preferences.recommended_threshold,
            "threshold_suggestion": preferences.get_threshold_suggestion()
        })
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def watering_history(request):
    """
    Get watering history for the user.
    """
    try:
        user = request.user
        # Get last 20 watering events (pump activations)
        history = SensorData.objects.filter(
            user=user,
            pump_status=True
        ).order_by('-timestamp')[:20]

        return Response([{
            "timestamp": data.timestamp.isoformat(),
            "duration": 5
        } for data in history])

    except Exception as e:
        logger.error(f"Error getting watering history: {e}")
        return Response({"error": str(e)}, status=500)


# Endpoint to handle notes
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_note(request):
    try:
        user = request.user
        note_text = request.data.get('note')

        if not note_text:
            return Response({"error": "Note text is required"}, status=status.HTTP_400_BAD_REQUEST)

        # In a real implementation, you would save to a Note model
        cache_key = f'notes_{user.id}'
        notes = cache.get(cache_key, [])
        notes.append({
            'text': note_text,
            'timestamp': timezone.now().isoformat()
        })
        cache.set(cache_key, notes, timeout=None)

        return Response({"status": "success"})

    except Exception as e:
        logger.error(f"Error adding note: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def schedule_irrigation(request, schedule_id=None):
    user = request.user

    # Check system mode and emergency status
    if request.method in ['POST', 'PUT', 'DELETE']:
        system_mode = cache.get(f'system_mode_{user.id}', False)
        emergency = cache.get(f'emergency_{user.id}', False)

        if not system_mode or emergency:
            return Response(
                {'error': 'Scheduling is only available in manual mode when no emergency is active'},
                status=status.HTTP_403_FORBIDDEN
            )

    # GET - List all schedules (always allowed)
    if request.method == 'GET':
        schedules = Schedule.objects.filter(user=user).order_by('scheduled_time')
        return Response([{
            'id': s.id,
            'scheduled_time': s.scheduled_time.isoformat(),
            'duration': s.duration,
            'is_active': s.is_active
        } for s in schedules])

    # POST - Create new schedule
    elif request.method == 'POST':
        try:
            data = request.data
            scheduled_time_str = data.get('scheduled_time')
            duration = int(data.get('duration', 15))

            if not scheduled_time_str:
                return Response({'error': 'Scheduled time is required'}, status=400)

            try:
                scheduled_time = datetime.fromisoformat(scheduled_time_str.replace('Z', '+00:00'))
            except ValueError:
                return Response({'error': 'Invalid datetime format'}, status=400)

            if scheduled_time < timezone.now():
                return Response({'error': 'Scheduled time must be in the future'}, status=400)

            schedule = Schedule.objects.create(
                user=user,
                scheduled_time=scheduled_time,
                duration=duration
            )

            return Response({
                'id': schedule.id,
                'scheduled_time': schedule.scheduled_time.isoformat(),
                'duration': schedule.duration
            }, status=201)

        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # PUT - Update existing schedule
    elif request.method == 'PUT' and schedule_id:
        try:
            schedule = Schedule.objects.get(id=schedule_id, user=user)
            data = request.data

            if 'scheduled_time' in data:
                try:
                    scheduled_time = datetime.fromisoformat(data['scheduled_time'].replace('Z', '+00:00'))
                    if scheduled_time < timezone.now():
                        return Response({'error': 'Scheduled time must be in the future'}, status=400)
                    schedule.scheduled_time = scheduled_time
                except ValueError:
                    return Response({'error': 'Invalid datetime format'}, status=400)

            if 'duration' in data:
                duration = int(data['duration'])
                if duration < 1 or duration > 120:
                    return Response({'error': 'Duration must be between 1-120 minutes'}, status=400)
                schedule.duration = duration

            schedule.save()
            return Response({
                'id': schedule.id,
                'scheduled_time': schedule.scheduled_time.isoformat(),
                'duration': schedule.duration
            })

        except Schedule.DoesNotExist:
            return Response({'error': 'Schedule not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # DELETE - Remove schedule
    elif request.method == 'DELETE' and schedule_id:
        try:
            schedule = Schedule.objects.get(id=schedule_id, user=user)
            schedule.delete()
            return Response({'status': 'success'})
        except Schedule.DoesNotExist:
            return Response({'error': 'Schedule not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    return Response({'error': 'Invalid request'}, status=400)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def schedule_list(request):
    """Handle listing and creation of schedules"""
    if request.method == 'GET':
        schedules = Schedule.objects.filter(user=request.user).order_by('scheduled_time')
        return Response([{
            'id': s.id,
            'scheduled_time': s.scheduled_time.astimezone(EAT).isoformat(),
            'duration': s.duration,
            'is_active': s.is_active
        } for s in schedules])

    elif request.method == 'POST':
        try:
            data = request.data
            scheduled_time_str = data.get('scheduled_time', None)
            duration = data.get('duration', None)

            # Validate required fields
            if not scheduled_time_str or not duration:
                return Response({'error': 'Scheduled time and duration are required'}, status=400)

            try:
                # Parse and convert to EAT timezone
                scheduled_time = datetime.fromisoformat(scheduled_time_str.replace('Z', '+00:00'))
                scheduled_time = scheduled_time.astimezone(EAT)
            except ValueError:
                return Response({'error': 'Invalid datetime format'}, status=400)

            if scheduled_time < timezone.now().astimezone(EAT):
                return Response({'error': 'Scheduled time must be in the future'}, status=400)

            schedule = Schedule.objects.create(
                user=request.user,
                scheduled_time=scheduled_time,
                duration=duration
            )

            return Response({
                'id': schedule.id,
                'scheduled_time': schedule.scheduled_time.astimezone(EAT).isoformat(),
                'duration': schedule.duration
            }, status=201)

        except Exception as e:
            return Response({'error': str(e)}, status=400)
    return None


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def schedule_detail(request, pk):
    """Handle retrieval, update and deletion of individual schedules"""
    schedule = get_object_or_404(Schedule, pk=pk, user=request.user)

    if request.method == 'GET':
        return Response({
            'id': schedule.id,
            'scheduled_time': schedule.scheduled_time.astimezone(EAT).isoformat(),
            'duration': schedule.duration,
            'is_active': schedule.is_active
        })

    elif request.method == 'PUT':
        try:
            data = request.data

            if 'scheduled_time' in data:
                try:
                    scheduled_time = datetime.fromisoformat(data['scheduled_time'].replace('Z', '+00:00'))
                    scheduled_time = scheduled_time.astimezone(EAT)
                    if scheduled_time < timezone.now().astimezone(EAT):
                        return Response({'error': 'Scheduled time must be in the future'}, status=400)
                    schedule.scheduled_time = scheduled_time
                except ValueError:
                    return Response({'error': 'Invalid datetime format'}, status=400)

            if 'duration' in data:
                duration = data['duration']
                if not duration:
                    return Response({'error': 'Duration cannot be empty'}, status=400)
                schedule.duration = duration

            schedule.save()
            return Response({
                'id': schedule.id,
                'scheduled_time': schedule.scheduled_time.astimezone(EAT).isoformat(),
                'duration': schedule.duration
            })

        except Exception as e:
            return Response({'error': str(e)}, status=400)

    elif request.method == 'DELETE':
        try:
            schedule.delete()
            return Response({'status': 'success'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def device_heartbeat(request):
    """
    Endpoint for devices to send periodic status updates
    """
    try:
        user = request.user
        data = request.data
        device_id = data.get('device_id', 'default_device')

        # Create or update device status
        status_data = {
            'system_mode': data.get('system_mode', 'auto'),
            'ip_address': request.META.get('REMOTE_ADDR'),
            'firmware': data.get('firmware', 'unknown')
        }

        device_status, created = DeviceStatus.objects.update_or_create(
            user=user,
            device_id=device_id,
            defaults={
                'operational_mode': status_data['system_mode'],
                'status_data': status_data,
                'ip_address': status_data['ip_address'],
                'firmware_version': status_data['firmware']
            }
        )

        # Update cache with latest status
        cache_keys = {
            f'device_{device_id}_status': status_data,
            f'device_{device_id}_last_seen': timezone.now().isoformat()
        }
        for key, value in cache_keys.items():
            cache.set(key, value, timeout=3600)  # 1 hour cache

        return Response({"status": "success", "device_id": device_id})

    except Exception as e:
        logger.error(f"[DEVICE HEARTBEAT] Error: {str(e)}", exc_info=True)
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Add these new API endpoints to your api.py file

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def receive_water_usage(request):
    """
    Receive water usage data from ESP32
    Expected data format:
    {
        'volume_used': 100,
        'initial_volume': 300,
        'final_volume': 200,
        'measurement_period_seconds': 43200,  # 12 hours in seconds
        'initial_level': 75,  # optional: percentage
        'final_level': 50     # optional: percentage
    }
    """
    logger.info(f"[WATER USAGE] Incoming data from {request.META.get('REMOTE_ADDR')}")

    try:
        data = request.data
        user = request.user

        # Calculate measurement period
        measurement_period = timedelta(seconds=data.get('measurement_period_seconds', 43200))

        # Save water usage record
        water_usage = WaterUsage.objects.create(
            user=user,
            volume_used=data.get('volume_used', 0),
            initial_volume=data.get('initial_volume', 0),
            final_volume=data.get('final_volume', 0),
            measurement_period=measurement_period
        )

        # Also save current tank level if provided
        if 'initial_level' in data and 'final_level' in data:
            # Save initial level (will have timestamp from when it was recorded)
            WaterTankLevel.objects.create(
                user=user,
                level_percentage=data.get('initial_level', 0),
                volume=data.get('initial_volume', 0),
                height=calculate_height_from_volume(data.get('initial_volume', 0)),
                timestamp=timezone.now() - measurement_period
            )

            # Save final level
            WaterTankLevel.objects.create(
                user=user,
                level_percentage=data.get('final_level', 0),
                volume=data.get('final_volume', 0),
                height=calculate_height_from_volume(data.get('final_volume', 0))
            )

        logger.info(f"[WATER USAGE] Saved: {water_usage.volume_used}L used over {measurement_period}")

        return Response({
            "status": "success",
            "water_usage_id": water_usage.id,
            "volume_used": water_usage.volume_used
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"[WATER USAGE ERROR] {str(e)}", exc_info=True)
        return Response({
            "status": "error",
            "message": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_water_usage_history(request):
    """
    Get water usage history for the user
    """
    try:
        user = request.user
        days = int(request.GET.get('days', 7))  # Default to last 7 days

        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get water usage records
        usage_records = WaterUsage.objects.filter(
            user=user,
            timestamp__gte=start_date,
            timestamp__lte=end_date
        ).order_by('-timestamp')

        # Calculate total usage
        total_usage = sum(record.volume_used for record in usage_records)

        # Format for response
        records_data = [{
            'id': record.id,
            'volume_used': record.volume_used,
            'initial_volume': record.initial_volume,
            'final_volume': record.final_volume,
            'measurement_period_hours': record.measurement_period.total_seconds() / 3600,
            'timestamp': record.timestamp.isoformat(),
            'date': record.timestamp.strftime('%Y-%m-%d'),
            'time': record.timestamp.strftime('%H:%M:%S')
        } for record in usage_records]

        return Response({
            'records': records_data,
            'total_usage': total_usage,
            'average_daily_usage': total_usage / days if days > 0 else 0,
            'period_days': days,
            'record_count': len(records_data)
        })

    except Exception as e:
        logger.error(f"[WATER USAGE HISTORY ERROR] {str(e)}", exc_info=True)
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_tank_level(request):
    """
    Get current water tank level
    """
    try:
        user = request.user
        latest_level = WaterTankLevel.objects.filter(user=user).order_by('-timestamp').first()

        if latest_level:
            return Response({
                'level_percentage': latest_level.level_percentage,
                'volume': latest_level.volume,
                'height': latest_level.height,
                'timestamp': latest_level.timestamp.isoformat()
            })
        else:
            return Response({
                'level_percentage': None,
                'volume': None,
                'height': None,
                'timestamp': None,
                'message': 'No tank level data available'
            })

    except Exception as e:
        logger.error(f"[TANK LEVEL ERROR] {str(e)}", exc_info=True)
        return Response({"error": str(e)}, status=500)


# Helper function to calculate height from volume
def calculate_height_from_volume(volume_liters):
    """
    Calculate water height in cm based on tank dimensions
    Tank: 400L capacity, 80cm height (from guide.txt)
    Volume to height conversion: height = (volume / max_volume) * max_height
    """
    MAX_VOLUME = 400  # liters
    MAX_HEIGHT = 80  # cm

    if volume_liters <= 0:
        return 0
    elif volume_liters >= MAX_VOLUME:
        return MAX_HEIGHT
    else:
        return (volume_liters / MAX_VOLUME) * MAX_HEIGHT


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_irrigation_frequency(request):
    """
    Get irrigation frequency analysis for the user
    """
    try:
        user = request.user
        days = int(request.GET.get('days', 30))  # Default to last 30 days

        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get irrigation events
        events = IrrigationEvent.objects.filter(
            user=user,
            start_time__gte=start_date,
            start_time__lte=end_date,
            completed=True
        ).order_by('start_time')

        if not events.exists() or events.count() < 2:
            return Response({
                'has_data': False,
                'message': 'Not enough irrigation data for analysis. Need at least 2 irrigation events.'
            })

        # Calculate intervals between irrigations
        intervals = []
        previous_time = None
        for event in events:
            if previous_time:
                interval_hours = (event.start_time - previous_time).total_seconds() / 3600
                intervals.append(interval_hours)
            previous_time = event.start_time

        # Calculate frequency metrics
        avg_interval = sum(intervals) / len(intervals) if intervals else 0
        min_interval = min(intervals) if intervals else 0
        max_interval = max(intervals) if intervals else 0

        # Group by day of week to find patterns
        events_by_weekday = defaultdict(list)
        for event in events:
            weekday = event.start_time.strftime('%A')  # Monday, Tuesday, etc.
            events_by_weekday[weekday].append(event)

        weekday_frequency = {}
        for day, day_events in events_by_weekday.items():
            weekday_frequency[day] = len(day_events)

        # Calculate moisture drop rate
        moisture_drops = []
        for event in events:
            if event.moisture_before and event.moisture_after:
                drop = event.moisture_before - event.moisture_after
                if drop > 0:
                    moisture_drops.append(drop)

        avg_moisture_drop = sum(moisture_drops) / len(moisture_drops) if moisture_drops else None

        # Estimate dry-out rate (% per hour)
        dry_out_rates = []
        for i in range(len(events) - 1):
            current_event = events[i]
            next_event = events[i + 1]
            if current_event.moisture_after and next_event.moisture_before:
                moisture_increase = next_event.moisture_before - current_event.moisture_after
                if moisture_increase > 0:  # Moisture increased between irrigations (rain?)
                    continue

                hours_between = (next_event.start_time - current_event.start_time).total_seconds() / 3600
                if hours_between > 0 and current_event.moisture_after > 0:
                    # Estimate how much moisture was lost per hour
                    # Assuming moisture returns to baseline after irrigation
                    rate = (current_event.moisture_after - next_event.moisture_before) / hours_between
                    if rate > 0:
                        dry_out_rates.append(rate)

        avg_dry_out_rate = sum(dry_out_rates) / len(dry_out_rates) if dry_out_rates else None

        # Calculate water usage trends
        total_water = sum(event.water_used_liters for event in events)
        avg_water_per_event = total_water / events.count() if events.exists() else 0

        # Project future water needs
        daily_irrigations = events.count() / days
        projected_weekly = daily_irrigations * 7 * avg_water_per_event
        projected_monthly = daily_irrigations * 30 * avg_water_per_event

        # Determine frequency status
        frequency_status = 'normal'
        if avg_interval < 12:  # Irrigating more than twice a day
            frequency_status = 'high'
        elif avg_interval > 72:  # Irrigating less than once every 3 days
            frequency_status = 'low'

        # Check for increasing trend (last 7 days vs previous 7 days)
        recent_start = end_date - timedelta(days=7)
        recent_events = events.filter(start_time__gte=recent_start).count()
        previous_events = events.filter(
            start_time__lt=recent_start,
            start_time__gte=start_date
        ).count()

        if recent_events > previous_events * 1.5 and previous_events > 0:
            frequency_status = 'increasing'

        # Generate recommendation
        recommendation = generate_irrigation_recommendation(
            user, avg_interval, avg_dry_out_rate,
            projected_weekly, events.count()
        )

        # Check if urgent stock alert is needed
        urgent_stock = False
        try:
            latest_tank = WaterTankLevel.objects.filter(user=user).latest('timestamp')
            if latest_tank.level_percentage < 20 and avg_interval < 24:
                urgent_stock = True
        except WaterTankLevel.DoesNotExist:
            pass

        # Prepare response
        response_data = {
            'has_data': True,
            'analysis_period_days': days,
            'total_irrigations': events.count(),
            'frequency_metrics': {
                'avg_interval_hours': round(avg_interval, 1),
                'min_interval_hours': round(min_interval, 1),
                'max_interval_hours': round(max_interval, 1),
                'avg_irrigations_per_day': round(events.count() / days, 2),
                'avg_interval_days': round(avg_interval / 24, 1)
            },
            'moisture_metrics': {
                'avg_moisture_drop': round(avg_moisture_drop, 1) if avg_moisture_drop else None,
                'avg_dry_out_rate': round(avg_dry_out_rate, 2) if avg_dry_out_rate else None,
                'estimated_time_to_dry': round(100 / avg_dry_out_rate, 1) if avg_dry_out_rate else None
            },
            'water_metrics': {
                'total_water_used': round(total_water, 1),
                'avg_water_per_irrigation': round(avg_water_per_event, 1),
                'projected_weekly_water': round(projected_weekly, 1),
                'projected_monthly_water': round(projected_monthly, 1)
            },
            'patterns': {
                'most_active_days': get_most_active_days(events_by_weekday),
                'frequency_status': frequency_status,
                'urgent_stock_alert': urgent_stock
            },
            'recommendation': recommendation,
            'events': [
                {
                    'id': e.id,
                    'date': e.start_time.astimezone(EAT).strftime('%Y-%m-%d'),
                    'time': e.start_time.astimezone(EAT).strftime('%H:%M'),
                    'duration': round(e.duration_minutes, 1) if e.duration_minutes else None,
                    'water_used': round(e.water_used_liters, 1),
                    'trigger': e.get_trigger_reason_display(),
                    'moisture_before': e.moisture_before,
                    'moisture_after': e.moisture_after
                }
                for e in events.order_by('-start_time')[:20]  # Last 20 events
            ]
        }

        # Save analysis to database
        analysis = IrrigationFrequencyAnalysis.objects.create(
            user=user,
            period_days=days,
            total_events=events.count(),
            avg_interval_hours=avg_interval,
            min_interval_hours=min_interval,
            max_interval_hours=max_interval,
            avg_water_per_event=avg_water_per_event,
            total_water_used=total_water,
            projected_weekly_water=projected_weekly,
            projected_monthly_water=projected_monthly,
            avg_moisture_drop_per_cycle=avg_moisture_drop,
            estimated_dry_out_rate=avg_dry_out_rate,
            frequency_status=frequency_status,
            recommendation=recommendation,
            urgent_stock_alert=urgent_stock
        )

        return Response(response_data)

    except Exception as e:
        logger.error(f"Error in irrigation frequency analysis: {e}")
        return Response({"error": str(e)}, status=500)


def generate_irrigation_recommendation(user, avg_interval, dry_out_rate, projected_weekly, event_count):
    """Generate personalized irrigation recommendation"""

    if avg_interval < 6:
        return (
            "⚠️ **VERY HIGH IRRIGATION FREQUENCY**\n\n"
            f"Your soil is being irrigated every {avg_interval:.1f} hours on average. "
            "This suggests the soil is drying out very quickly. Possible causes:\n"
            "• Very sandy soil with poor water retention\n"
            "• High temperatures or low humidity\n"
            "• Plants at peak water consumption stage\n\n"
            "📋 **Recommendations:**\n"
            "1. Consider adding organic matter to improve soil water retention\n"
            "2. Apply mulch to reduce evaporation\n"
            "3. Check for leaks in your irrigation system\n"
            "4. Monitor plants for signs of overwatering\n\n"
            f"💧 **Water Alert:** You're using ~{projected_weekly:.0f}L per week. "
            "Ensure you have adequate water stock."
        )

    elif avg_interval < 24:
        return (
            "🔔 **MODERATE IRRIGATION FREQUENCY**\n\n"
            f"Your system irrigates every {avg_interval:.1f} hours (roughly "
            f"{24 / avg_interval:.1f} times per day). This is typical for many crops.\n\n"
            "📋 **Recommendations:**\n"
            "1. Monitor if frequency increases during hot weather\n"
            "2. Keep track of weekly water usage patterns\n"
            "3. Consider if your crop is at peak water demand stage\n\n"
            f"💧 **Planning:** Based on current usage, you'll need about "
            f"{projected_weekly:.0f}L for the next week."
        )

    elif avg_interval < 72:
        return (
            "✅ **LOW IRRIGATION FREQUENCY**\n\n"
            f"Your system irrigates every {avg_interval:.1f} hours "
            f"(~{48 / avg_interval:.1f} times every 2 days). Your soil retains water well.\n\n"
            "📋 **Recommendations:**\n"
            "1. Continue current practices\n"
            "2. Monitor during hot/dry spells as frequency may increase\n"
            "3. This pattern is good for water conservation\n\n"
            f"💧 Your weekly water needs are approximately {projected_weekly:.0f}L."
        )

    else:
        return (
            "🌵 **VERY LOW IRRIGATION FREQUENCY**\n\n"
            f"Your system irrigates every {avg_interval:.1f} hours "
            f"(~{72 / avg_interval:.1f} times every 3 days). This could indicate:\n"
            "• Drought-tolerant crops\n"
            "• Excellent soil water retention\n"
            "• Possibly not enough water for thirsty plants\n\n"
            "📋 **Recommendations:**\n"
            "1. Ensure plants aren't showing signs of water stress\n"
            "2. Check soil moisture manually to verify readings\n"
            "3. Consider if irrigation threshold is set too low\n\n"
            f"💧 Your weekly water usage is about {projected_weekly:.0f}L."
        )


def get_most_active_days(events_by_weekday):
    """Find which days have most irrigation events"""
    if not events_by_weekday:
        return []

    sorted_days = sorted(
        events_by_weekday.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )

    return [
        {'day': day, 'count': len(events)}
        for day, events in sorted_days[:3]  # Top 3 days
    ]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_water_stock_alert(request):
    """
    Generate water stock alert based on irrigation frequency
    """
    try:
        user = request.user

        # Get latest tank level
        try:
            latest_tank = WaterTankLevel.objects.filter(user=user).latest('timestamp')
            current_level = latest_tank.volume
            current_percentage = latest_tank.level_percentage
        except WaterTankLevel.DoesNotExist:
            return Response({
                'has_data': False,
                'message': 'No tank level data available'
            })

        # Get recent irrigation frequency (last 7 days)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=7)

        recent_events = IrrigationEvent.objects.filter(
            user=user,
            start_time__gte=start_date,
            completed=True
        )

        if not recent_events.exists():
            return Response({
                'has_data': False,
                'message': 'Not enough irrigation data to generate alert'
            })

        # Calculate average daily usage
        total_water_used = sum(event.water_used_liters for event in recent_events)
        avg_daily_usage = total_water_used / 7

        # Calculate average irrigations per day
        avg_irrigations_per_day = recent_events.count() / 7

        # Estimate days remaining
        if avg_daily_usage > 0:
            days_remaining = current_level / avg_daily_usage
        else:
            days_remaining = float('inf')

        # Estimate irrigations remaining
        avg_water_per_event = total_water_used / recent_events.count() if recent_events.exists() else 0
        irrigations_remaining = int(current_level / avg_water_per_event) if avg_water_per_event > 0 else 0

        # Determine if urgent action needed
        urgent = False
        if current_percentage < 15 or days_remaining < 2:
            urgent = True

        # Calculate recommended stock date and amount
        recommended_stock_date = timezone.now() + timedelta(days=max(1, int(days_remaining * 0.7)))
        recommended_stock_amount = avg_daily_usage * 14  # Recommend 2 weeks worth

        # Create alert record
        alert = WaterStockAlert.objects.create(
            user=user,
            current_tank_level=current_level,
            estimated_days_remaining=days_remaining,
            estimated_irrigations_remaining=irrigations_remaining,
            avg_daily_usage=avg_daily_usage,
            avg_irrigations_per_day=avg_irrigations_per_day,
            recommended_stock_date=recommended_stock_date.date(),
            recommended_stock_amount=recommended_stock_amount,
            urgent_action_needed=urgent,
            notification_sent=False
        )

        # Send SMS alert if urgent and user has notifications enabled
        if urgent and user.receive_sms_alerts and user.phone_number:
            try:
                from .sms import send_stock_alert
                send_stock_alert(user, alert)
                alert.notification_sent = True
                alert.save()
            except Exception as e:
                logger.error(f"Failed to send stock alert SMS: {e}")

        # Generate alert message
        if urgent:
            status = "⚠️ **URGENT WATER STOCK ALERT**"
            message = (
                f"Your water level is critically low at {current_percentage:.1f}% "
                f"({current_level:.1f}L). Based on your irrigation frequency "
                f"({avg_irrigations_per_day:.1f} irrigations/day), you have approximately "
                f"{days_remaining:.1f} days of water remaining.\n\n"
                f"**Immediate Action Required:** Stock up on water within the next 2 days!"
            )
        else:
            status = "📊 **Water Stock Forecast**"
            message = (
                f"Based on your irrigation frequency, you have approximately "
                f"{days_remaining:.1f} days of water remaining ({irrigations_remaining} irrigations).\n\n"
                f"Current level: {current_percentage:.1f}% ({current_level:.1f}L)\n"
                f"Average daily usage: {avg_daily_usage:.1f}L\n"
                f"Recommended to stock up by: {recommended_stock_date.date()}"
            )

        return Response({
            'has_data': True,
            'urgent': urgent,
            'status': status,
            'message': message,
            'current_level': round(current_level, 1),
            'current_percentage': round(current_percentage, 1),
            'avg_daily_usage': round(avg_daily_usage, 1),
            'avg_irrigations_per_day': round(avg_irrigations_per_day, 1),
            'days_remaining': round(days_remaining, 1),
            'irrigations_remaining': irrigations_remaining,
            'recommended_stock_date': recommended_stock_date.date().isoformat(),
            'recommended_stock_amount': round(recommended_stock_amount, 1),
            'alert_id': alert.id
        })

    except Exception as e:
        logger.error(f"Error in water stock alert: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_irrigation_event(request):
    """
    Record an irrigation event (called when pump turns on/off)
    """
    try:
        user = request.user
        action = request.data.get('action')  # 'start' or 'end'
        event_id = request.data.get('event_id')

        if action == 'start':
            # Start new irrigation event
            event = IrrigationEvent.objects.create(
                user=user,
                start_time=timezone.now(),
                trigger_reason=request.data.get('trigger', 'auto_low_moisture'),
                moisture_before=request.data.get('moisture_before'),
                completed=False
            )
            return Response({
                'status': 'success',
                'event_id': event.id,
                'message': 'Irrigation event started'
            })

        elif action == 'end' and event_id:
            # End irrigation event
            try:
                event = IrrigationEvent.objects.get(id=event_id, user=user)
                event.end_time = timezone.now()

                # Calculate duration
                if event.start_time:
                    duration = (event.end_time - event.start_time).total_seconds() / 60
                    event.duration_minutes = duration

                # Calculate water used (if flow rate known)
                flow_rate = request.data.get('flow_rate_lpm', 2.0)  # Default 2L/min
                if event.duration_minutes:
                    event.water_used_liters = event.duration_minutes * flow_rate

                event.moisture_after = request.data.get('moisture_after')
                event.completed = True
                event.save()

                return Response({
                    'status': 'success',
                    'duration': round(event.duration_minutes, 1),
                    'water_used': round(event.water_used_liters, 1),
                    'message': 'Irrigation event completed'
                })

            except IrrigationEvent.DoesNotExist:
                return Response({'error': 'Event not found'}, status=404)

        return Response({'error': 'Invalid action'}, status=400)

    except Exception as e:
        logger.error(f"Error recording irrigation event: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_irrigation_predictions(request):
    """
    Predict future irrigation needs based on historical patterns
    """
    try:
        user = request.user
        days_ahead = int(request.GET.get('days_ahead', 7))

        # Get historical data (last 60 days)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=60)

        events = IrrigationEvent.objects.filter(
            user=user,
            start_time__gte=start_date,
            completed=True
        ).order_by('start_time')

        if not events.exists() or events.count() < 5:
            return Response({
                'has_data': False,
                'message': 'Need more irrigation history for predictions'
            })

        # Calculate daily averages
        daily_counts = defaultdict(int)
        daily_water = defaultdict(float)

        for event in events:
            day_key = event.start_time.date()
            daily_counts[day_key] += 1
            daily_water[day_key] += event.water_used_liters

        # Calculate average irrigations per day
        avg_daily_irrigations = sum(daily_counts.values()) / len(daily_counts)
        avg_daily_water = sum(daily_water.values()) / len(daily_water)

        # Check for seasonal patterns (simplified)
        # Group by month to see if irrigation increases
        monthly_counts = defaultdict(int)
        for event in events:
            month_key = event.start_time.strftime('%Y-%m')
            monthly_counts[month_key] += 1

        # Calculate trend (increasing/decreasing)
        months = sorted(monthly_counts.keys())
        trend = 'stable'
        if len(months) >= 2:
            last_month = monthly_counts[months[-1]]
            prev_month = monthly_counts[months[-2]]
            if last_month > prev_month * 1.3:
                trend = 'increasing'
            elif last_month < prev_month * 0.7:
                trend = 'decreasing'

        # Generate predictions
        predictions = []
        running_water_needed = 0

        for day in range(1, days_ahead + 1):
            pred_date = (timezone.now() + timedelta(days=day)).date()

            # Adjust prediction based on trend
            multiplier = 1.0
            if trend == 'increasing':
                multiplier = 1.0 + (day * 0.02)  # 2% increase per day
            elif trend == 'decreasing':
                multiplier = max(0.5, 1.0 - (day * 0.01))  # 1% decrease per day

            predicted_irrigations = avg_daily_irrigations * multiplier
            predicted_water = avg_daily_water * multiplier

            running_water_needed += predicted_water

            predictions.append({
                'date': pred_date.isoformat(),
                'predicted_irrigations': round(predicted_irrigations, 1),
                'predicted_water_liters': round(predicted_water, 1)
            })

        return Response({
            'has_data': True,
            'trend': trend,
            'avg_daily_irrigations': round(avg_daily_irrigations, 1),
            'avg_daily_water_liters': round(avg_daily_water, 1),
            'predictions': predictions,
            'total_predicted_water': round(running_water_needed, 1),
            'confidence': 'high' if events.count() > 30 else 'medium'
        })

    except Exception as e:
        logger.error(f"Error in irrigation predictions: {e}")
        return Response({"error": str(e)}, status=500)

