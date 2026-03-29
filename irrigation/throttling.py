from rest_framework.throttling import SimpleRateThrottle


class DeviceRateThrottle(SimpleRateThrottle):
    scope = 'device'
    rate = '12/minute'  # Explicit rate for clarity

    def get_cache_key(self, request, view):
        if hasattr(request, 'auth') and request.auth:
            # Use API key + endpoint as cache key
            return f'throttle_device_{request.auth}_{view.__class__.__name__}'
        return None  # No throttling if no auth

    @property
    def throttle_success(self):
        # Add Retry-After header when throttling
        response = super().throttle_success
        if not response:
            return response

        # Calculate remaining time
        history = self.history
        if len(history) >= self.num_requests:
            wait = int((history[-1] - history[0]) + 1)
            self.wait = wait

        return response
