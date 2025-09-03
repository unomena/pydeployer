"""
Celery configuration for PyDeployer
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pydeployer.settings')

# Create the Celery app
app = Celery('pydeployer')

# Load configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    'cleanup-stuck-deployments': {
        'task': 'deployer.tasks.cleanup_stuck_deployments',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
    'check-deployment-health': {
        'task': 'deployer.tasks.check_deployment_health',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}

# Configure task routing
app.conf.task_routes = {
    'deployer.tasks.*': {'queue': 'deployments'},
}

# Set task time limits
app.conf.task_time_limit = 1800  # 30 minutes
app.conf.task_soft_time_limit = 1500  # 25 minutes

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')