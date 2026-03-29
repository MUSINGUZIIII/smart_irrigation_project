from rest_framework import authentication
from rest_framework import exceptions
from accounts.models import CustomUser


class APIKeyAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_API_KEY')
        if not api_key:
            return None

        try:
            user = CustomUser.objects.get(api_key=api_key)
        except CustomUser.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid API key')

        return user, None
