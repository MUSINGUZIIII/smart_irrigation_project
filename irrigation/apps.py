from django.apps import AppConfig
import logging
import threading
import os
from django.db import connection

logger = logging.getLogger(__name__)


class IrrigationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'irrigation'

    def __init__(self, app_name, app_module):
        super().__init__(app_name, app_module)
        self._pid = None

    def ready(self):
        # Pre-load AI models when Django starts
        from irrigation.services.knowledge.guide_bot import IrrigationGuide
        self.guide_system = IrrigationGuide()
        # Only initialize once per process
        if not hasattr(self, '_pid') or self._pid != os.getpid():
            self._pid = os.getpid()
            logger.info(f"App ready in PID {os.getpid()}")