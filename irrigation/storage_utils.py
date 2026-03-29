from django.conf import settings
from django.core.files.storage import get_storage_class


def get_custom_storage():
    """Get the appropriate storage backend"""
    if getattr(settings, 'IS_PRODUCTION', False):
        # Check if Cloudinary is configured
        cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', None)
        if cloud_name:
            try:
                from cloudinary_storage.storage import MediaCloudinaryStorage
                return MediaCloudinaryStorage()
            except ImportError:
                pass

    # Fallback to default storage
    from django.core.files.storage import default_storage
    return default_storage


# Create storage instance
custom_storage = get_custom_storage()

