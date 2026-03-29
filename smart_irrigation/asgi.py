import os
import sys
from django.core.asgi import get_asgi_application

# Check if we're on Windows
IS_WINDOWS = sys.platform.startswith('win')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_irrigation.settings')

if IS_WINDOWS:
    # Windows: Use standard ASGI without Channels to avoid non-blocking I/O issues
    print("Windows detected: Using standard ASGI application (Channels disabled)")
    application = get_asgi_application()
else:
    # Linux/Mac: Use Channels with WebSocket support
    try:
        from channels.routing import ProtocolTypeRouter, URLRouter
        from channels.auth import AuthMiddlewareStack
        from channels.security.websocket import AllowedHostsOriginValidator
        import irrigation.routing

        print("Linux/Mac detected: Using Channels with WebSocket support")

        application = ProtocolTypeRouter({
            "http": get_asgi_application(),
            "websocket": AllowedHostsOriginValidator(
                AuthMiddlewareStack(
                    URLRouter(
                        irrigation.routing.websocket_urlpatterns
                    )
                )
            ),
        })
    except ImportError:
        print("Channels not available, falling back to standard ASGI")
        application = get_asgi_application()
