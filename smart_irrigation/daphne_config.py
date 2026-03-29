"""
Daphne configuration for Windows compatibility.
"""
import os
import sys
import warnings

# Windows-specific fixes
if sys.platform.startswith('win'):
    # Set environment variable to allow async unsafe operations
    os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')

    # Suppress specific warnings
    warnings.filterwarnings("ignore",
                            message=".*set_nonblocking.*",
                            category=RuntimeWarning)
    warnings.filterwarnings("ignore",
                            message=".*async.*",
                            category=RuntimeWarning)

    # Apply Windows-specific event loop policy
    try:
        import asyncio

        if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except ImportError:
        pass

# Import after Windows fixes
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_irrigation.settings')

# Get the ASGI application
django_application = get_asgi_application()

# Export for Daphne
application = django_application
