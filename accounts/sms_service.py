from django.core.checks import messages
from django.shortcuts import redirect
from django.utils import timezone
from accounts.helper_code import generate_verification_code
from accounts.models import CustomUser
from irrigation.sms import SMSService


def send_verification_sms(phone_number, code):
    """Send SMS verification code using EgoSMS"""
    message = (
        f"Smart Irrigation Password Reset\n"
        f"Verification code: {code}\n"
        f"Valid for 10 minutes\n\n"
        f"Enter this code to reset your password.\n"
        f"If you didn't request this, please ignore."
    )

    print(f"DEBUG: Preparing to send SMS to {phone_number}")
    print(f"DEBUG: Message content: {message}")

    # Use your existing SMSService that works with EgoSMS
    success, response = SMSService.send_direct_sms(phone_number, message)

    print(f"DEBUG: SMS send result - Success: {success}, Response: '{response}'")

    # EgoSMS returns "OK" for success - check both the success flag and response text
    if success or (isinstance(response, str) and response.strip().upper() == "OK"):
        print("DEBUG: SMS sent successfully based on response")
        return True
    else:
        print(f"DEBUG: SMS failed based on response: {response}")
        return False


def send_password_reset_sms(phone_number, reset_url):
    """Send password reset link via SMS"""
    message = (
        f"Password reset requested.\n"
        f"Click here: {reset_url}\n"
        f"Or enter code sent separately."
    )

    success, response = SMSService.send_direct_sms(phone_number, message)

    # FIX: Handle EgoSMS response properly
    if response.strip().upper() == "OK":
        return True
    else:
        return False


def password_reset_sms_resend(request):
    user_id = request.session.get('sms_verification_user_id')
    if not user_id:
        messages.error(request, "Session expired. Please start over.")
        return redirect('password_reset_sms_quick')

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
            messages.error(request, "Failed to send SMS. Please try again.")

    except CustomUser.DoesNotExist:
        messages.error(request, "Session expired. Please start over.")

    return redirect('password_reset_sms_verify')
