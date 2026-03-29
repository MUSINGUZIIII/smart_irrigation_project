from django.db import connections, close_old_connections
from contextlib import contextmanager
import threading
import os

_local = threading.local()


@contextmanager
def acquire_connection():
    # Create fresh connection for each thread/process
    if hasattr(_local, 'connection'):
        close_old_connections()
        del _local.connection

    _local.connection = connections.create_connection('default')
    _local.pid = os.getpid()

    try:
        yield _local.connection
    finally:
        try:
            if hasattr(_local, 'connection') and _local.pid == os.getpid():
                close_old_connections()
                del _local.connection
        except:
            pass
