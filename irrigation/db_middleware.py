import os
from django.core.files.storage import default_storage
from django.db import close_old_connections
from django.core.exceptions import MiddlewareNotUsed
from smart_irrigation import settings

IS_PRODUCTION = os.getenv('ENVIRONMENT') == 'production'


class DBConnectionMiddleware:
    def __init__(self, get_response):
        if IS_PRODUCTION:
            raise MiddlewareNotUsed
        self.get_response = get_response

    def __call__(self, request):
        close_old_connections()
        response = self.get_response(request)
        close_old_connections()
        return response


class VerifyStorageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Just log the storage issue, don't try to fix it
        if settings.IS_PRODUCTION:
            from django.core.files.storage import default_storage
            storage_class = str(default_storage.__class__)
            if 'cloudinary' not in storage_class.lower():
                print(f"WARNING: Not using Cloudinary storage. Current storage: {storage_class}")
                print("DEBUG: Using URL fallback instead of trying to fix storage")

        response = self.get_response(request)
        return response

