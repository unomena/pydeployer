from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from core.models import (
    Project, Environment, Deployment, Service,
    DeploymentLog, HealthCheck, WebhookEvent
)
from .serializers import (
    ProjectSerializer, EnvironmentSerializer, DeploymentSerializer,
    ServiceSerializer, DeploymentLogSerializer, HealthCheckSerializer,
    WebhookEventSerializer, DeployRequestSerializer, RollbackRequestSerializer,
    ServiceActionSerializer, ProjectRegisterSerializer
)
from deployer.executor import DeploymentExecutor
from deployer.supervisor import SupervisorManager
import logging
import secrets

logger = logging.getLogger('deployer')


class ProjectViewSet(viewsets.ModelViewSet):
    """ViewSet for managing projects"""
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        # Generate webhook secret
        webhook_secret = secrets.token_urlsafe(32)
        serializer.save(webhook_secret=webhook_secret)
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new project"""
        serializer = ProjectRegisterSerializer(data=request.data)
        if serializer.is_valid():
            # Check if project already exists
            if Project.objects.filter(name=serializer.validated_data['name']).exists():
                return Response(
                    {'error': 'Project with this name already exists'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create project
            project = Project.objects.create(
                **serializer.validated_data,
                webhook_secret=secrets.token_urlsafe(32)
            )
            
            # Create default environments
            for env_name in ['qa', 'stage', 'prod']:
                Environment.objects.create(
                    project=project,
                    name=env_name
                )
            
            return Response(
                ProjectSerializer(project).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def sync_repository(self, request, pk=None):
        """Sync repository for a project"""
        project = self.get_object()
        try:
            from deployer.git_manager import GitManager
            git_manager = GitManager()
            
            repo_path = f"/opt/deployments/repos/{project.name}"
            git_manager.fetch(repo_path)
            
            return Response({'status': 'Repository synced successfully'})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EnvironmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing environments"""
    queryset = Environment.objects.all()
    serializer_class = EnvironmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset


class DeploymentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing deployments"""
    queryset = Deployment.objects.all()
    serializer_class = DeploymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by project
        project = self.request.query_params.get('project')
        if project:
            queryset = queryset.filter(environment__project__name=project)
        
        # Filter by environment
        environment = self.request.query_params.get('environment')
        if environment:
            queryset = queryset.filter(environment__name=environment)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def deploy(self, request):
        """Trigger a new deployment"""
        serializer = DeployRequestSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            
            try:
                # Get project and environment
                project = get_object_or_404(Project, name=data['project'])
                environment = get_object_or_404(
                    Environment,
                    project=project,
                    name=data['environment']
                )
                
                # Check if deployment is already in progress
                if environment.deployments.filter(
                    status__in=['pending', 'cloning', 'building', 'deploying', 'testing']
                ).exists():
                    return Response(
                        {'error': 'Deployment already in progress for this environment'},
                        status=status.HTTP_409_CONFLICT
                    )
                
                # Execute deployment
                executor = DeploymentExecutor()
                deployment = executor.deploy(
                    project_name=data['project'],
                    environment_name=data['environment'],
                    commit_sha=data.get('commit_sha'),
                    deployed_by=data.get('deployed_by', request.user.username)
                )
                
                return Response(
                    DeploymentSerializer(deployment).data,
                    status=status.HTTP_201_CREATED
                )
                
            except Project.DoesNotExist:
                return Response(
                    {'error': f"Project '{data['project']}' not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Environment.DoesNotExist:
                return Response(
                    {'error': f"Environment '{data['environment']}' not found for project '{data['project']}'"},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                logger.error(f"Deployment failed: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def rollback(self, request):
        """Rollback to previous deployment"""
        serializer = RollbackRequestSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            
            try:
                executor = DeploymentExecutor()
                deployment = executor.rollback(
                    project_name=data['project'],
                    environment_name=data['environment'],
                    deployed_by=data.get('deployed_by', request.user.username)
                )
                
                return Response(
                    DeploymentSerializer(deployment).data,
                    status=status.HTTP_200_OK
                )
                
            except Exception as e:
                logger.error(f"Rollback failed: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Get deployment logs"""
        deployment = self.get_object()
        logs = deployment.logs.all()
        
        # Filter by level if specified
        level = request.query_params.get('level')
        if level:
            logs = logs.filter(level=level)
        
        serializer = DeploymentLogSerializer(logs, many=True)
        return Response(serializer.data)


class ServiceViewSet(viewsets.ModelViewSet):
    """ViewSet for managing services"""
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by project
        project = self.request.query_params.get('project')
        if project:
            queryset = queryset.filter(environment__project__name=project)
        
        # Filter by environment
        environment = self.request.query_params.get('environment')
        if environment:
            queryset = queryset.filter(environment__name=environment)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def service_action(self, request, pk=None):
        """Perform action on service (start/stop/restart)"""
        service = self.get_object()
        serializer = ServiceActionSerializer(data=request.data)
        
        if serializer.is_valid():
            action_type = serializer.validated_data['action']
            supervisor = SupervisorManager()
            
            try:
                if action_type == 'start':
                    supervisor.start_service(service.supervisor_name)
                    service.status = 'running'
                elif action_type == 'stop':
                    supervisor.stop_service(service.supervisor_name)
                    service.status = 'stopped'
                elif action_type in ['restart', 'reload']:
                    supervisor.reload_service(service.supervisor_name)
                    service.status = 'running'
                
                service.save()
                
                return Response({
                    'status': f'Service {action_type} successful',
                    'service': ServiceSerializer(service).data
                })
                
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def health_checks(self, request, pk=None):
        """Get health check history for service"""
        service = self.get_object()
        health_checks = service.health_checks.all()[:100]  # Last 100 checks
        serializer = HealthCheckSerializer(health_checks, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def check_health(self, request, pk=None):
        """Perform health check on service"""
        service = self.get_object()
        
        if service.service_type != 'django' or not service.health_check_endpoint:
            return Response(
                {'error': 'Health check not configured for this service'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            import requests
            url = f"http://127.0.0.1:{service.port}{service.health_check_endpoint}"
            response = requests.get(url, timeout=5)
            
            health_check = HealthCheck.objects.create(
                service=service,
                is_healthy=response.status_code == 200,
                response_time=response.elapsed.total_seconds(),
                error_message='' if response.status_code == 200 else f'Status: {response.status_code}'
            )
            
            service.last_health_check = timezone.now()
            service.save()
            
            return Response(HealthCheckSerializer(health_check).data)
            
        except Exception as e:
            health_check = HealthCheck.objects.create(
                service=service,
                is_healthy=False,
                error_message=str(e)
            )
            
            service.last_health_check = timezone.now()
            service.save()
            
            return Response(
                HealthCheckSerializer(health_check).data,
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class StatusViewSet(viewsets.ViewSet):
    """ViewSet for system status"""
    permission_classes = [AllowAny]  # Public endpoint for health checks
    
    def list(self, request):
        """Get overall system status"""
        status_data = {
            'projects': Project.objects.filter(active=True).count(),
            'environments': Environment.objects.filter(active=True).count(),
            'active_deployments': Deployment.objects.filter(status='active').count(),
            'running_services': Service.objects.filter(status='running').count(),
            'failed_services': Service.objects.filter(status='failed').count(),
            'recent_deployments': DeploymentSerializer(
                Deployment.objects.all()[:10],
                many=True
            ).data,
            'unhealthy_services': ServiceSerializer(
                Service.objects.filter(
                    health_checks__is_healthy=False,
                    health_checks__timestamp__gte=timezone.now() - timezone.timedelta(hours=1)
                ).distinct(),
                many=True
            ).data
        }
        
        return Response(status_data)