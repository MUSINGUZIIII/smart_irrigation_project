"""Django's command-line utility for administrative tasks (Windows version)."""
import os
import sys
import warnings


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_irrigation.settings')

    # Windows-specific fixes
    if sys.platform.startswith('win'):
        os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')
        warnings.filterwarnings("ignore",
                                message=".*set_nonblocking.*",
                                category=RuntimeWarning)

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
