from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from .views import (
    ProjectViewSet, EnvironmentViewSet, DeploymentViewSet,
    ServiceViewSet, StatusViewSet
)
from .health import health_check

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'environments', EnvironmentViewSet)
router.register(r'deployments', DeploymentViewSet)
router.register(r'services', ServiceViewSet)
router.register(r'status', StatusViewSet, basename='status')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token/', obtain_auth_token, name='api_token_auth'),
    
    # Public health check endpoint
    path('health/', health_check, name='api_health'),
    
    # Convenience endpoints
    path('deploy/', DeploymentViewSet.as_view({'post': 'deploy'}), name='api_deploy'),
    path('rollback/', DeploymentViewSet.as_view({'post': 'rollback'}), name='api_rollback'),
]