from django.conf import settings


def get_media_url(file_field):
    """Get media URL that works with both local and Cloudinary storage"""
    if not file_field:
        return None

    try:
        # First try to get URL from storage
        url = file_field.url
        print(f"DEBUG: Storage URL: {url}")

        # If we're in production but got a local URL, convert to Cloudinary URL
        if (settings.IS_PRODUCTION and
                url and url.startswith('/media/') and
                hasattr(settings, 'CLOUDINARY_CLOUD_NAME') and
                settings.CLOUDINARY_CLOUD_NAME):

            filename = file_field.name
            # Remove 'media/' prefix if present
            if filename.startswith('media/'):
                filename = filename[6:]

            # Create Cloudinary URL
            cloudinary_url = f'https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}/image/upload/{filename}'
            print(f"DEBUG: Converted to Cloudinary URL: {cloudinary_url}")
            return cloudinary_url

        return url

    except Exception as e:
        print(f"Error getting media URL: {e}")
        return None
