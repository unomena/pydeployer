"""
Celery tasks for deployment processing
"""
import logging
from celery import shared_task
from django.utils import timezone
from core.models import Deployment
from .executor import DeploymentExecutor

logger = logging.getLogger('deployer')


@shared_task(bind=True, max_retries=0)
def process_deployment(self, deployment_id):
    """Process a deployment asynchronously"""
    try:
        deployment = Deployment.objects.get(id=deployment_id)
        
        # Check if deployment is still pending
        if deployment.status != 'pending':
            logger.info(f"Deployment {deployment_id} is not pending (status: {deployment.status}), skipping")
            return f"Deployment {deployment_id} already processed"
        
        # Mark as deploying
        deployment.status = 'deploying'
        deployment.save()
        
        logger.info(f"Starting async deployment {deployment_id} for {deployment.environment}")
        
        # Execute the deployment
        executor = DeploymentExecutor()
        
        # Run the actual deployment steps
        try:
            executor._execute_deployment_steps(deployment)
            
            # Mark as successful
            deployment.status = 'active'
            deployment.completed_at = timezone.now()
            deployment.save()
            
            # Deactivate previous deployments
            deployment.environment.deployments.exclude(id=deployment.id).filter(
                status='active'
            ).update(status='inactive')
            
            logger.info(f"Deployment {deployment_id} completed successfully")
            return f"Deployment {deployment_id} completed successfully"
            
        except Exception as e:
            deployment.status = 'failed'
            deployment.error_message = str(e)
            deployment.completed_at = timezone.now()
            deployment.save()
            logger.error(f"Deployment {deployment_id} failed: {str(e)}")
            raise
            
    except Deployment.DoesNotExist:
        logger.error(f"Deployment {deployment_id} not found")
        return f"Deployment {deployment_id} not found"
    except Exception as e:
        logger.error(f"Error processing deployment {deployment_id}: {str(e)}")
        raise


@shared_task
def cleanup_stuck_deployments():
    """Clean up stuck deployments (running for more than 30 minutes)"""
    from datetime import timedelta
    
    threshold = timezone.now() - timedelta(minutes=30)
    stuck = Deployment.objects.filter(
        status__in=['pending', 'deploying'],
        deployed_at__lt=threshold
    )
    
    for deployment in stuck:
        logger.warning(f"Cleaning up stuck deployment {deployment.id}")
        deployment.status = 'failed'
        deployment.error_message = 'Deployment timed out after 30 minutes'
        deployment.completed_at = timezone.now()
        deployment.save()
    
    return f"Cleaned up {stuck.count()} stuck deployments"


@shared_task
def check_deployment_health():
    """Check health of active deployments"""
    from core.models import Environment
    
    for env in Environment.objects.filter(active=True):
        deployment = env.get_current_deployment()
        if deployment and deployment.status == 'active':
            # Trigger health check
            try:
                executor = DeploymentExecutor()
                executor._perform_health_checks(env, deployment)
            except Exception as e:
                logger.error(f"Health check failed for {env}: {str(e)}")
    
    return "Health checks completed"