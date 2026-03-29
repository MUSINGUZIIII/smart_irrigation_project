import os
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_POST
from rest_framework.authtoken.models import Token
from django.views.decorators.csrf import csrf_protect
from irrigation.models import SensorData
from irrigation.sms import SMSService
from smart_irrigation import settings
from .forms import CustomUserCreationForm, CustomUserChangeForm, NotificationPreferencesForm
from .helper_code import generate_verification_code
from .models import CustomUser, validate_phone_number
from .utils import send_brevo_transactional_email
from django.db import transaction
from irrigation.db_utils import acquire_connection
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import SMSVerificationForm, PhoneNumberForm
from .sms_service import send_verification_sms


def home(request):
    return render(request, 'accounts/home.html')


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            with acquire_connection() as connection:
                with transaction.atomic(using=connection.alias):
                    user = form.save(commit=False)
                    user.set_password(form.cleaned_data['password1'])
                    user.save()
                    login(request, user)
                    messages.success(request, 'Registration successful. Welcome!')
                    return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'You have been logged in successfully.')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'accounts/login.html')


@login_required
def profile(request):
    if request.method == 'POST':
        # Check if this is a profile picture only upload
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and 'profile_picture' in request.FILES:
            return handle_profile_picture_upload(request)

        form = CustomUserChangeForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            try:
                user = form.save()

                # Return appropriate response based on request type
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    profile_picture_url = user.get_profile_picture_url()
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Profile updated successfully',
                        'profile_picture_url': profile_picture_url,
                        'phone_number': user.phone_number
                    })

                messages.success(request, 'Profile updated successfully.')
                return redirect('profile')
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'status': 'error',
                        'message': str(e)
                    }, status=400)
                messages.error(request, f'Error updating profile: {str(e)}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': 'Form validation failed',
                    'errors': form.errors.get_json_data()
                }, status=400)
            messages.error(request, 'Please correct the errors below.')

    else:
        form = CustomUserChangeForm(instance=request.user)

    # Get profile picture URL safely
    profile_picture_url = request.user.get_profile_picture_url()

    return render(request, 'accounts/profile.html', {
        'form': form,
        'user': request.user,
        'profile_picture_url': profile_picture_url
    })


def handle_profile_picture_upload(request):
    """Handle AJAX profile picture uploads separately"""
    try:
        print(f"DEBUG: Starting profile picture upload for user {request.user.username}")

        profile_picture = request.FILES['profile_picture']
        print(f"DEBUG: Received file: {profile_picture.name}, size: {profile_picture.size}")

        # Flag For Uploading a profile picture
        request.user._uploading_profile_picture = True

        # Validate file size (10MB max)
        if profile_picture.size > 10 * 1024 * 1024:
            print("DEBUG: File too large")
            return JsonResponse({
                'status': 'error',
                'message': 'Image file too large ( > 10MB )'
            }, status=400)

        # Validate file type
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
        ext = os.path.splitext(profile_picture.name)[1].lower()
        if ext not in valid_extensions:
            print(f"DEBUG: Invalid file extension: {ext}")
            return JsonResponse({
                'status': 'error',
                'message': 'Unsupported file extension. Please use .jpg, .jpeg, .png, or .gif'
            }, status=400)

        # Save new profile picture
        print(f"DEBUG: Setting profile picture for user {request.user.username}")
        request.user.profile_picture = profile_picture

        # Save the user instance
        request.user.save()
        print(f"DEBUG: User saved with profile picture name: {request.user.profile_picture.name if request.user.profile_picture else 'None'}")

        # Safe debug for path - handle case where profile_picture is None
        if request.user.profile_picture and hasattr(request.user.profile_picture, 'path'):
            print(f"DEBUG: Profile picture path: {request.user.profile_picture.path}")
        else:
            print("DEBUG: Profile picture path: No path available")

        # Refresh from database to ensure we have the latest data
        from django.db import transaction
        with transaction.atomic():
            updated_user = CustomUser.objects.get(pk=request.user.pk)
            profile_picture_url = updated_user.get_profile_picture_url()
            print(f"DEBUG: After refresh - Profile picture name: {updated_user.profile_picture.name if updated_user.profile_picture else 'None'}")
            print(f"DEBUG: After refresh - Profile picture URL: {profile_picture_url}")

        return JsonResponse({
            'status': 'success',
            'message': 'Profile picture updated successfully',
            'profile_picture_url': profile_picture_url,
            'profile_picture_name': updated_user.profile_picture.name if updated_user.profile_picture else None
        })

    except Exception as e:
        print(f"DEBUG: Error in profile picture upload: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)


def user_logout(request):
    logout(request)
    return redirect('home')


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'accounts/change_password.html', {'form': form})


@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, 'Your account has been successfully deleted.')
        return redirect('home')
    return render(request, 'accounts/delete_account.html')


def password_reset_request(request):
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            associated_users = CustomUser.objects.filter(email=email)

            if associated_users.exists():
                user = associated_users.first()

                # Store email in session for later use
                request.session['reset_email'] = email

                # Check if user has a phone number
                if user.phone_number:
                    # Redirect to phone number confirmation
                    return redirect('password_reset_confirm_phone')
                else:
                    # Fall back to email
                    return send_password_reset_email(request, user)

            # Always return success to prevent email enumeration
            return redirect("password_reset_done")
    else:
        form = PasswordResetForm()

    return render(request, "accounts/password_reset.html", {"form": form})


@login_required
def confirm_token_regeneration(request):
    return render(request, 'accounts/confirm_token_regeneration.html')


def password_reset_sms_choice(request):
    email = request.session.get('reset_email')
    if not email:
        return redirect('password_reset')

    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        return redirect('password_reset')

    if request.method == 'POST':
        if 'use_sms' in request.POST and user.phone_number:
            # Generate and send SMS code
            code = generate_verification_code()
            user.sms_verification_code = code
            user.sms_verification_sent_at = timezone.now()
            user.sms_verification_attempts = 0
            user.save()

            # Send SMS
            success = send_verification_sms(user.phone_number, code)

            if success:
                request.session['sms_verification_user_id'] = user.id
                return redirect('password_reset_sms_verify')
            else:
                messages.error(request, "Failed to send SMS. Please try email instead.")
                return send_password_reset_email(request, user)

        elif 'use_email' in request.POST:
            return send_password_reset_email(request, user)

    return render(request, 'accounts/password_reset_choice.html', {
        'user': user,
        'phone_number': user.phone_number[-4:] if user.phone_number else None
    })


def password_reset_sms_verify(request):
    """Page where user enters the 6-digit verification code"""
    user_id = request.session.get('sms_verification_user_id')
    print(f"DEBUG: In verification page, user_id from session: {user_id}")

    if not user_id:
        messages.error(request, "Session expired. Please start over.")
        return redirect('password_reset_sms_quick')

    try:
        user = CustomUser.objects.get(id=user_id)
        print(f"DEBUG: Found user for verification: {user.username}")
    except CustomUser.DoesNotExist:
        messages.error(request, "Invalid session. Please start over.")
        return redirect('password_reset_sms_quick')

    # Check if code is expired (10 minutes)
    if (user.sms_verification_sent_at and
            (timezone.now() - user.sms_verification_sent_at) > timedelta(minutes=10)):
        messages.error(request, "Verification code has expired.")
        return redirect('password_reset_sms_quick')

    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        print(f"DEBUG: User entered code: {code}")

        # Check attempts
        if user.sms_verification_attempts >= 3:
            messages.error(request, "Too many attempts. Please request a new code.")
            return redirect('password_reset_sms_quick')

        if len(code) != 6 or not code.isdigit():
            messages.error(request, "Please enter a valid 6-digit code.")
        elif user.sms_verification_code == code:
            # Code is correct - allow password reset
            print("DEBUG: Code is correct!")
            request.session['verified_user_id'] = user.id
            user.sms_verification_code = None
            user.sms_verification_attempts = 0
            user.save()
            return redirect('password_reset_confirm_sms')
        else:
            # Wrong code
            user.sms_verification_attempts += 1
            user.save()
            messages.error(request, f"Invalid code. {3 - user.sms_verification_attempts} attempts remaining.")

    return render(request, 'accounts/password_reset_sms_verify.html', {
        'user': user,
        'phone_number': user.phone_number[-4:] if user.phone_number else '****'
    })


def password_reset_confirm_sms(request):
    user_id = request.session.get('verified_user_id')
    if not user_id:
        return redirect('password_reset')

    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return redirect('password_reset')

    if request.method == 'POST':
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            # Clear session
            request.session.pop('verified_user_id', None)
            messages.success(request, "Your password has been reset successfully.")
            # AFTER PASSWORD RESET, REDIRECT TO LOGIN
            return redirect('password_reset_complete')
    else:
        form = SetPasswordForm(user)

    return render(request, 'accounts/password_reset_confirm_sms.html', {'form': form})


def send_password_reset_email(request, user):
    # Your existing email sending logic
    current_site = get_current_site(request)
    subject = "Password Reset Request"
    email_template = "accounts/password_reset_email.html"

    context = {
        'email': user.email,
        'domain': current_site.domain,
        'site_name': current_site.name,
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        'user': user,
        'token': default_token_generator.make_token(user),
        'protocol': 'https' if request.is_secure() else 'http',
    }

    email_content = render_to_string(email_template, context)

    if send_brevo_transactional_email(user.email, subject, email_content):
        return redirect("password_reset_done")
    else:
        messages.error(request, "Failed to send password reset email. Please try again later.")
        return redirect("password_reset")


@require_POST
@csrf_protect
@login_required
def regenerate_api_key(request):
    if 'confirm' not in request.POST:
        # If not confirmed, redirect to confirmation page
        return redirect('confirm_token_regeneration')

    if request.POST['confirm'] == 'yes':
        # Delete the old token
        Token.objects.filter(user=request.user).delete()
        # Create a new token
        new_token = Token.objects.create(user=request.user)

        # If AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': 'API token regenerated successfully',
                'new_api_token': new_token.key
            })

        # For regular form submission
        messages.success(request, 'Your API token has been regenerated successfully.')
        return redirect('profile')

    # If confirmation was 'no'
    messages.info(request, 'Token regeneration cancelled. Your current token remains active.')
    return redirect('profile')


@require_POST
@csrf_protect
@login_required
def cleanup_broken_image(request):
    """Clean up reference to broken profile picture"""
    if request.user.is_authenticated and request.user.profile_picture:
        try:
            # Verify the image is actually broken by trying to access it
            request.user.profile_picture.url
            return JsonResponse({'status': 'info', 'message': 'Image exists'})
        except Exception as e:
            # Image is broken - remove the reference
            request.user.profile_picture = None
            request.user.save()
            return JsonResponse({'status': 'success', 'message': 'Broken image reference removed'})

    return JsonResponse({'status': 'info', 'message': 'No image to clean up'})


def default_avatar(request, cloudinary_url=None):
    """Serve a default avatar image"""
    # Try to use Cloudinary first
    if settings.IS_PRODUCTION:
        try:
            from cloudinary import CloudinaryImage
            cloudinary_img = CloudinaryImage("media/default_avatar")
            # Redirect to Cloudinary URL
            from django.shortcuts import redirect
            return redirect(cloudinary_url.build_url())
        except:
            # Fall back to local avatar
            pass

    # Serve local default avatar (SVG)
    svg_avatar = '''<svg xmlns="http://www.w3.org/2000/svg" width="150" height="150" viewBox="0 0 150 150">
        <circle cx="75" cy="60" r="30" fill="#cccccc" stroke="#999999" stroke-width="3"/>
        <circle cx="75" cy="150" r="50" fill="#cccccc" stroke="#999999" stroke-width="3"/>
        <text x="75" y="85" text-anchor="middle" fill="#999999" font-family="Arial, sans-serif" font-size="14">Avatar</text>
    </svg>'''

    return HttpResponse(svg_avatar, content_type='image/svg+xml')


@login_required
def check_profile_picture(request):
    """Check the status of the current user's profile picture"""
    profile_picture_url = request.user.get_profile_picture_url()

    return JsonResponse({
        'has_profile_picture': bool(profile_picture_url),
        'profile_picture_url': profile_picture_url,
        'profile_picture_name': request.user.profile_picture.name if request.user.profile_picture else None
    })


@login_required
def regenerate_profile_picture_url(request):
    """Regenerate profile picture URL to fix double extensions"""
    if request.user.profile_picture:
        # Get the current filename
        current_filename = request.user.profile_picture.name

        # Fix double extensions
        if has_double_extension(current_filename):
            fixed_filename = fix_filename(current_filename)

            # Update the user
            request.user.profile_picture.name = fixed_filename
            request.user.save()

            return JsonResponse({
                'status': 'success',
                'message': 'Profile picture URL fixed',
                'new_url': request.user.get_profile_picture_url()
            })

    return JsonResponse({
        'status': 'info',
        'message': 'No fix needed'
    })


def has_double_extension(filename):
    """Check if filename has double extensions"""
    import os
    basename = os.path.basename(filename)
    name_parts = basename.split('.')

    if len(name_parts) > 2:
        extensions = ['jpg', 'jpeg', 'png', 'gif']
        if name_parts[-1].lower() in extensions and name_parts[-2].lower() in extensions:
            return True
    return False


def fix_filename(filename):
    """Fix double extensions in filename"""
    import os
    basename = os.path.basename(filename)
    dirname = os.path.dirname(filename)

    name_parts = basename.split('.')

    if len(name_parts) > 2:
        # Keep the first part and the last extension
        fixed_basename = f"{'.'.join(name_parts[:-2])}.{name_parts[-1]}"
        return os.path.join(dirname, fixed_basename)

    return filename


@login_required
def notification_settings(request):
    if request.method == 'POST':
        form = NotificationPreferencesForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()

            # Send test SMS if user just enabled notifications
            if form.cleaned_data.get('receive_sms_alerts'):
                # Check if user has phone number
                if not request.user.phone_number:
                    messages.warning(request,
                                     'SMS alerts enabled but no phone number configured. '
                                     'Please add your phone number in profile settings.')
                    return redirect('notification_settings')

                try:
                    latest_data = SensorData.objects.latest('timestamp')
                    success, message = SMSService.send_alert(request.user, latest_data)

                    if success:
                        messages.success(request, 'Notification preferences saved! Test SMS sent successfully.')
                    else:
                        # Provide more specific error message
                        if "Invalid phone number" in message:
                            messages.warning(request,
                                             'Preferences saved, but phone number format is invalid. '
                                             'Please update your phone number in profile settings.')
                        elif "Network error" in message:
                            messages.warning(request,
                                             'Preferences saved, but network error occurred. '
                                             'Please check your internet connection.')
                        else:
                            messages.warning(request, f'Preferences saved, but test SMS failed: {message}')

                except SensorData.DoesNotExist:
                    messages.info(request, 'Preferences saved. No sensor data available for test message.')
                except Exception as e:
                    messages.error(request, f'Error sending test SMS: {str(e)}')
            else:
                messages.success(request, 'Notification preferences saved! SMS alerts disabled.')

            return redirect('notification_settings')
    else:
        form = NotificationPreferencesForm(instance=request.user)

    return render(request, 'accounts/notification_settings.html', {'form': form})


@login_required
def send_test_sms(request):
    """Send a test SMS immediately"""
    if request.method == 'POST':
        try:
            # Get latest sensor data
            latest_data = SensorData.objects.latest('timestamp')
            success, message = SMSService.send_alert(request.user, latest_data)

            if success:
                messages.success(request, 'Test SMS sent successfully!')
            else:
                messages.error(request, f'Failed to send test SMS: {message}')
        except Exception as e:
            messages.error(request, f'Error sending test SMS: {str(e)}')

    return redirect('notification_settings')


def password_reset_sms_resend(request):
    user_id = request.session.get('sms_verification_user_id')
    if not user_id:
        return redirect('password_reset')

    try:
        user = CustomUser.objects.get(id=user_id)

        # Generate new code
        code = generate_verification_code()
        user.sms_verification_code = code
        user.sms_verification_sent_at = timezone.now()
        user.sms_verification_attempts = 0
        user.save()

        # Send new SMS
        success = send_verification_sms(user.phone_number, code)

        if success:
            messages.success(request, "New verification code sent!")
        else:
            messages.error(request, "Failed to send SMS. Please try email instead.")
            return send_password_reset_email(request, user)

    except CustomUser.DoesNotExist:
        messages.error(request, "Session expired. Please start over.")

    return redirect('password_reset_sms_verify')


def password_reset_sms_quick(request):
    """Quick SMS password reset from login page with better phone number handling"""
    print(f"DEBUG: password_reset_sms_quick called, method: {request.method}")

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', '').strip()
        print(f"DEBUG: Raw phone number input: '{phone_number}'")

        if phone_number:
            # Clean and normalize the input phone number
            from irrigation.sms import SMSService
            clean_phone = SMSService.clean_phone_number(phone_number)
            print(f"DEBUG: Cleaned phone number: '{clean_phone}'")

            if clean_phone:
                # Find user by phone number - try multiple formats
                users = find_users_by_phone(clean_phone)
                print(f"DEBUG: Found {users.count()} users with matching phone number")

                if users.exists():
                    user = users.first()
                    print(f"DEBUG: User found: {user.username}, ID: {user.id}, DB phone: '{user.phone_number}'")

                    # Generate verification code
                    code = generate_verification_code()
                    print(f"DEBUG: Generated code: {code}")

                    # Update user with verification code
                    user.sms_verification_code = code
                    user.sms_verification_sent_at = timezone.now()
                    user.sms_verification_attempts = 0
                    user.save()

                    # Send SMS
                    success, message = SMSService.send_direct_sms(clean_phone, f"Your verification code: {code}")
                    print(f"DEBUG: SMS sent - Success: {success}, Response: {message}")

                    # Handle EgoSMS response
                    if success or (isinstance(message, str) and message.strip().upper() == "OK"):
                        print("DEBUG: SMS sent successfully")
                        request.session['sms_verification_user_id'] = user.id
                        request.session.modified = True
                        print(f"DEBUG: Redirecting to verification page with user_id: {user.id}")
                        return redirect('password_reset_sms_verify')
                    else:
                        messages.error(request, f"SMS sending failed: {message}")
                else:
                    # Show helpful error with phone number formats tried
                    show_phone_lookup_help(request, phone_number, clean_phone)
            else:
                messages.error(request, "Invalid phone number format. Please use format: +256712345678")
        else:
            messages.error(request, "Please enter a phone number.")

    # Show the form
    return render(request, 'accounts/password_reset_quick.html')


def find_users_by_phone(phone_number):
    """Find users by phone number using multiple formatting approaches"""
    from irrigation.sms import SMSService

    # Try different phone number formats
    possible_formats = [
        phone_number,  # Original cleaned format
        phone_number.replace('+', ''),  # Without +
        phone_number.replace('+', '0'),  # Replace + with 0
        '0' + phone_number[3:] if phone_number.startswith('+256') else None,  # +2567... -> 07...
    ]

    # Remove None values and duplicates
    possible_formats = list(set([fmt for fmt in possible_formats if fmt]))

    print(f"DEBUG: Searching phone formats: {possible_formats}")

    # Query for users with any of these phone numbers
    users = CustomUser.objects.filter(phone_number__in=possible_formats)

    # If still no users found, try partial matching
    if not users.exists():
        # Remove country code and search for local number
        local_number = phone_number
        if phone_number.startswith('+256'):
            local_number = phone_number[4:]  # Remove +256
        elif phone_number.startswith('256'):
            local_number = phone_number[3:]  # Remove 256

        if local_number != phone_number:
            users = CustomUser.objects.filter(phone_number__endswith=local_number)

    return users


def show_phone_lookup_help(request, original_phone, cleaned_phone):
    """Show helpful debug information about phone number lookup"""
    print(f"DEBUG: PHONE LOOKUP FAILED")
    print(f"DEBUG: Original input: '{original_phone}'")
    print(f"DEBUG: Cleaned format: '{cleaned_phone}'")

    # Show all users with phone numbers for debugging
    users_with_phones = CustomUser.objects.exclude(phone_number__isnull=True).exclude(phone_number='')
    print("DEBUG: All users with phone numbers in database:")
    for user in users_with_phones:
        print(f"DEBUG: - {user.username}: '{user.phone_number}'")

    messages.error(request,
                   f"No account found with phone number: {original_phone}. "
                   f"Registered numbers: {', '.join([user.phone_number for user in users_with_phones[:3]])}"
                   f"{'...' if users_with_phones.count() > 3 else ''}"
                   )


def password_reset_confirm_phone(request):
    """Confirm or enter phone number for SMS reset"""
    email = request.session.get('reset_email')
    if not email:
        return redirect('password_reset')

    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        return redirect('password_reset')

    if request.method == 'POST':
        # Get the phone number (either from form or user's saved number)
        phone_number = request.POST.get('phone_number', user.phone_number)

        if phone_number:
            # Validate phone number
            try:
                validate_phone_number(phone_number)

                # Update user's phone number if different
                if user.phone_number != phone_number:
                    user.phone_number = phone_number
                    user.save()

                # Generate and send SMS code
                code = generate_verification_code()
                user.sms_verification_code = code
                user.sms_verification_sent_at = timezone.now()
                user.sms_verification_attempts = 0
                user.save()

                # Send SMS using EgoSMS
                success = send_verification_sms(user.phone_number, code)

                if success:
                    request.session['sms_verification_user_id'] = user.id
                    messages.success(request, "Verification code sent to your phone!")
                    return redirect('password_reset_sms_verify')
                else:
                    messages.error(request, "Failed to send SMS. Please try email instead.")
                    return send_password_reset_email(request, user)

            except ValidationError:
                messages.error(request, "Please enter a valid phone number.")
        else:
            messages.error(request, "Phone number is required for SMS reset.")

    return render(request, 'accounts/password_reset_confirm_phone.html', {
        'user': user,
        'has_existing_phone': bool(user.phone_number)
    })


def debug_sms_test(request):
    """Test SMS sending directly"""
    test_phone = "+256780443345"  # Test number
    code = generate_verification_code()
    success = send_verification_sms(test_phone, code)
    return JsonResponse({'success': success, 'code': code})


def debug_verify_test(request):
    """Test that verification page works"""
    # Create a test user session
    test_user = CustomUser.objects.first()
    if test_user:
        request.session['sms_verification_user_id'] = test_user.id
        return redirect('password_reset_sms_verify')
    return HttpResponse("No test user found")
