"""
PyDeployer - Zero-downtime deployment orchestration system
"""

# Import Celery app for shared_task decorators
from .celery import app as celery_app

__all__ = ('celery_app',)
__version__ = '1.0.0'