import os
import sys
from celery import Celery

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_irrigation.settings')

# Check if we're on Windows
IS_WINDOWS = sys.platform.startswith('win')

# Create Celery app with Windows-compatible settings
if IS_WINDOWS:
    app = Celery('smart_irrigation')
    # Windows-specific settings
    app.conf.update(
        worker_pool='solo',
        task_always_eager=False,
        broker_connection_retry_on_startup=True,
    )
else:
    app = Celery('smart_irrigation')
    # Linux/Mac settings
    app.conf.update(
        worker_pool='prefork',
        broker_connection_retry_on_startup=True,
    )

# Load task modules from all registered Django apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
