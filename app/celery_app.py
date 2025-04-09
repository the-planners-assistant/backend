# app/celery_app.py
from celery import Celery
from app.core.config import settings

# Initialize Celery
# The first argument is the name of the current module (__name__ could work)
# The 'broker' and 'backend' arguments point to your Redis instance using config
celery_app = Celery(
    "tasks", # Can be any name, often the name of the tasks module
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=['app.tasks'] # List modules where tasks are defined
)

# Optional Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/London', # Set your timezone
    enable_utc=True,
    task_track_started=True, # Useful for seeing 'STARTED' status
    result_expires=3600, # How long to keep results in backend (1 hour)
)

if __name__ == '__main__':
    # This allows running celery directly using 'python -m app.celery_app worker'
    celery_app.start()