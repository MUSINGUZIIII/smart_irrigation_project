@echo off
REM Start Redis (if not already running)
start redis-server

REM Start Celery worker with eventlet pool (Windows compatible)
start celery -A smart_irrigation worker --loglevel=info --pool=eventlet --concurrency=4

REM Start Celery beat
start celery -A smart_irrigation beat --loglevel=info

REM Keep window open
pause
