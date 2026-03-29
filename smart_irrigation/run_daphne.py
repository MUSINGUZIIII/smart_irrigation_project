"""
Windows-compatible Daphne runner.
"""
import os
import sys
import warnings

# Add Windows-specific fixes
if sys.platform.startswith('win'):
    # Set environment variables for Windows compatibility
    os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')

    # Suppress warnings
    warnings.filterwarnings("ignore",
                            message=".*set_nonblocking.*",
                            category=RuntimeWarning)
    warnings.filterwarnings("ignore",
                            message=".*async.*",
                            category=RuntimeWarning)

# Import Daphne
try:
    from daphne.cli import CommandLineInterface
except ImportError:
    print("Daphne is not installed. Install with: pip install daphne")
    sys.exit(1)

if __name__ == "__main__":
    # Use the Windows-compatible config
    sys.argv.extend([
        "smart_irrigation.daphne_config:application",
        "--bind", "0.0.0.0",
        "--port", "8000",
        "--verbosity", "2"
    ])

    # Run Daphne
    CommandLineInterface().run()
    