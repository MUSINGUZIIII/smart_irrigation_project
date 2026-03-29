from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseNotFound
from django.conf import settings


class ThrottleHeaderMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if response.status_code == 429 and hasattr(request, 'throttled'):
            if hasattr(request.throttled, 'wait'):
                response['Retry-After'] = int(request.throttled.wait)
        return response


def block_media_requests_in_production(get_response):
    def middleware(request):
        # Check if this is a media request in production
        if (settings.IS_PRODUCTION and
                request.path.startswith(settings.MEDIA_URL) and
                not request.path.endswith(('.jpg', '.jpeg', '.png', '.gif'))):  # Don't block image requests
            return HttpResponseNotFound("Media files are served through Cloudinary")

        response = get_response(request)
        return response

    return middleware

