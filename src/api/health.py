from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from core.models import Project, Environment, Deployment, Service


@csrf_exempt
def health_check(request):
    """Public health check endpoint"""
    try:
        # Basic database check
        Project.objects.exists()
        
        status_data = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'projects': Project.objects.filter(active=True).count(),
            'environments': Environment.objects.filter(active=True).count(),
            'active_deployments': Deployment.objects.filter(status='active').count(),
            'running_services': Service.objects.filter(status='running').count(),
            'failed_services': Service.objects.filter(status='failed').count(),
        }
        
        return JsonResponse(status_data)
        
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=503)