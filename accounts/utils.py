from sib_api_v3_sdk import ApiClient, Configuration, TransactionalEmailsApi
from sib_api_v3_sdk.models import SendSmtpEmail, SendSmtpEmailSender, SendSmtpEmailTo

import logging

from smart_irrigation import settings

logger = logging.getLogger(__name__)


def send_brevo_transactional_email(to_email, subject, html_content):
    """
    Send email via Brevo API
    Returns True if successful, False otherwise
    """
    config = Configuration()
    config.api_key['api-key'] = settings.BREVO_API_KEY

    api_instance = TransactionalEmailsApi(ApiClient(config))

    sender = SendSmtpEmailSender(
        email=settings.DEFAULT_FROM_EMAIL,
        name="Smart Irrigation System"
    )
    to = [SendSmtpEmailTo(email=to_email)]

    email = SendSmtpEmail(
        sender=sender,
        to=to,
        subject=subject,
        html_content=html_content,
    )

    try:
        api_response = api_instance.send_transac_email(email)
        logger.info(f"Email sent to {to_email}. Message ID: {api_response.message_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False


def get_cloudinary_url(file_field):
    """Get Cloudinary URL for a file field"""
    if not file_field:
        return None

    try:
        if settings.IS_PRODUCTION:
            from cloudinary import CloudinaryImage

            # Extract public_id from file path - KEEP THE FILE EXTENSION
            public_id = file_field.name

            # Remove 'media/' prefix if present
            if public_id.startswith('media/'):
                public_id = public_id[6:]

            print(f"DEBUG: Generating Cloudinary URL for public_id: {public_id}")

            # Generate Cloudinary URL with the original file extension
            img = CloudinaryImage(public_id)

            # Build URL with proper format - use the original file extension
            url = img.build_url(
                # Don't force format, let Cloudinary use the original
                quality='auto',
                fetch_format='auto',
                secure=True
            )

            print(f"DEBUG: Generated Cloudinary URL: {url}")
            return url
        else:
            # Local development
            return file_field.url
    except Exception as e:
        print(f"Error generating Cloudinary URL: {e}")
        return None
