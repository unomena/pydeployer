from rest_framework import serializers
from core.models import (
    Project, Environment, Deployment, Service,
    DeploymentLog, HealthCheck, WebhookEvent
)


class ProjectSerializer(serializers.ModelSerializer):
    environments_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'repository_url', 'default_branch', 'port_start',
            'webhook_secret', 'active', 'description', 'created_at', 
            'updated_at', 'environments_count'
        ]
        read_only_fields = ['webhook_secret', 'created_at', 'updated_at']
    
    def get_environments_count(self, obj):
        return obj.environments.count()


class EnvironmentSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    current_deployment = serializers.SerializerMethodField()
    services_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Environment
        fields = [
            'id', 'project', 'project_name', 'name', 'config', 'secrets',
            'active', 'domain', 'ssl_enabled', 'created_at', 'updated_at',
            'current_deployment', 'services_count'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_current_deployment(self, obj):
        deployment = obj.get_current_deployment()
        if deployment:
            return {
                'id': deployment.id,
                'version': deployment.version,
                'status': deployment.status,
                'deployed_at': deployment.deployed_at
            }
        return None
    
    def get_services_count(self, obj):
        return obj.services.count()


class DeploymentSerializer(serializers.ModelSerializer):
    environment_name = serializers.CharField(source='environment.name', read_only=True)
    project_name = serializers.CharField(source='environment.project.name', read_only=True)
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = Deployment
        fields = [
            'id', 'environment', 'environment_name', 'project_name', 'version',
            'commit_sha', 'commit_message', 'commit_author', 'commit_date',
            'status', 'deployment_path', 'deployed_by', 'deployed_at',
            'completed_at', 'error_message', 'duration'
        ]
        read_only_fields = [
            'deployment_path', 'deployed_at', 'completed_at'
        ]
    
    def get_duration(self, obj):
        if obj.completed_at and obj.deployed_at:
            delta = obj.completed_at - obj.deployed_at
            return delta.total_seconds()
        return None


class ServiceSerializer(serializers.ModelSerializer):
    environment_name = serializers.CharField(source='environment.name', read_only=True)
    project_name = serializers.CharField(source='environment.project.name', read_only=True)
    
    class Meta:
        model = Service
        fields = [
            'id', 'environment', 'environment_name', 'project_name', 'name',
            'service_type', 'command', 'port', 'status', 'pid', 'memory_usage',
            'cpu_usage', 'last_health_check', 'health_check_endpoint',
            'supervisor_name', 'enabled', 'max_memory', 'max_cpu',
            'restart_count', 'last_restart'
        ]
        read_only_fields = [
            'supervisor_name', 'pid', 'memory_usage', 'cpu_usage',
            'last_health_check', 'restart_count', 'last_restart'
        ]


class DeploymentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeploymentLog
        fields = ['id', 'deployment', 'timestamp', 'level', 'message', 'details']
        read_only_fields = ['timestamp']


class HealthCheckSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.name', read_only=True)
    
    class Meta:
        model = HealthCheck
        fields = [
            'id', 'service', 'service_name', 'timestamp', 'is_healthy',
            'response_time', 'error_message'
        ]
        read_only_fields = ['timestamp']


class WebhookEventSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    
    class Meta:
        model = WebhookEvent
        fields = [
            'id', 'project', 'project_name', 'event_type', 'payload',
            'headers', 'processed', 'deployment', 'error_message',
            'received_at', 'processed_at'
        ]
        read_only_fields = ['received_at', 'processed_at']


class DeployRequestSerializer(serializers.Serializer):
    """Serializer for deployment requests"""
    project = serializers.CharField(required=True)
    environment = serializers.ChoiceField(choices=['qa', 'stage', 'prod'], required=True)
    commit_sha = serializers.CharField(required=False, allow_blank=True)
    commit_message = serializers.CharField(required=False, allow_blank=True)
    commit_author = serializers.CharField(required=False, allow_blank=True)
    deployed_by = serializers.CharField(required=False, default='api')


class RollbackRequestSerializer(serializers.Serializer):
    """Serializer for rollback requests"""
    project = serializers.CharField(required=True)
    environment = serializers.ChoiceField(choices=['qa', 'stage', 'prod'], required=True)
    deployed_by = serializers.CharField(required=False, default='api')


class ServiceActionSerializer(serializers.Serializer):
    """Serializer for service actions"""
    action = serializers.ChoiceField(
        choices=['start', 'stop', 'restart', 'reload'],
        required=True
    )


class ProjectRegisterSerializer(serializers.Serializer):
    """Serializer for registering new projects"""
    name = serializers.CharField(required=True)
    repository_url = serializers.URLField(required=True)
    default_branch = serializers.CharField(required=False, default='main')
    port_start = serializers.IntegerField(required=True, min_value=1024, max_value=65535)
    deploy_key = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)