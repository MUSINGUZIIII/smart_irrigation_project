"""
Windows-compatible Celery worker.
"""
import os
import sys
import warnings

# Windows-specific fixes
if sys.platform.startswith('win'):
    os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')
    warnings.filterwarnings("ignore",
                            message=".*set_nonblocking.*",
                            category=RuntimeWarning)

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_irrigation.settings')

# Import and setup Django
import django

django.setup()

# Now import Celery
from smart_irrigation.celery_setup import app

if __name__ == '__main__':
    # Windows-specific worker options
    if sys.platform.startswith('win'):
        argv = [
            'worker',
            '--pool=solo',  # Use solo pool for Windows
            '--loglevel=info',
            '--concurrency=1'
        ]
    else:
        argv = [
            'worker',
            '--loglevel=info',
            '--concurrency=4'
        ]

    # Start Celery worker
    app.worker_main(argv)
