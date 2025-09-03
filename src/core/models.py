from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from cryptography.fernet import Fernet
import json
import os


class EncryptedJSONField(models.JSONField):
    """Custom field to store encrypted JSON data"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cipher = None
    
    @property
    def cipher(self):
        """Lazy load cipher to ensure ENCRYPTION_KEY is available"""
        if self._cipher is None:
            key = os.environ.get('ENCRYPTION_KEY')
            if not key:
                # Try to load from .env file if available
                env_file = '/srv/deployments/apps/pydeployer/releases/initial/.env'
                if os.path.exists(env_file):
                    with open(env_file) as f:
                        for line in f:
                            if line.startswith('ENCRYPTION_KEY='):
                                key = line.split('=', 1)[1].strip()
                                break
                
                if not key:
                    # Generate a default key if none is provided (for migrations)
                    key = Fernet.generate_key().decode()
                    print(f"WARNING: No ENCRYPTION_KEY found, using temporary key. Set ENCRYPTION_KEY in environment.")
            
            try:
                self._cipher = Fernet(key.encode() if isinstance(key, str) else key)
            except ValueError as e:
                # If the key is invalid, generate a new one
                print(f"WARNING: Invalid ENCRYPTION_KEY: {e}. Generating new key.")
                key = Fernet.generate_key().decode()
                self._cipher = Fernet(key.encode())
        
        return self._cipher
    
    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        try:
            # If value looks like encrypted data (base64 string), decrypt it
            if isinstance(value, str) and len(value) > 20 and '=' in value:
                decrypted = self.cipher.decrypt(value.encode())
                return json.loads(decrypted.decode())
            else:
                # Not encrypted, parse as JSON
                return json.loads(value) if isinstance(value, str) else value
        except Exception as e:
            # If decryption fails, return empty dict as fallback
            return {}
    
    def to_python(self, value):
        if isinstance(value, dict):
            return value
        if value is None:
            return value
        try:
            # If value looks like encrypted data (base64 string), decrypt it
            if isinstance(value, str) and len(value) > 20 and '=' in value:
                decrypted = self.cipher.decrypt(value.encode())
                return json.loads(decrypted.decode())
            else:
                # Not encrypted, parse as JSON
                return json.loads(value) if isinstance(value, str) else value
        except Exception as e:
            # If decryption fails, return empty dict as fallback
            return {}
    
    def get_prep_value(self, value):
        if value is None:
            return value
        json_str = json.dumps(value)
        encrypted = self.cipher.encrypt(json_str.encode())
        return encrypted.decode()


class Project(models.Model):
    """Represents a deployable project"""
    name = models.CharField(max_length=100, unique=True, db_index=True)
    repository_url = models.URLField(help_text="Git repository URL")
    deploy_key = models.TextField(blank=True, null=True, default='', help_text="SSH key for private repositories")
    default_branch = models.CharField(max_length=100, default='main')
    port_start = models.IntegerField(help_text="Starting port for service allocation")
    webhook_secret = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'deployer_projects'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_next_available_port(self, environment):
        """Get next available port for a service"""
        used_ports = Service.objects.filter(
            environment__project=self,
            environment__name=environment
        ).values_list('port', flat=True)
        
        port = self.port_start
        while port in used_ports:
            port += 1
        return port


class Environment(models.Model):
    """Environment configuration for a project"""
    ENVIRONMENT_CHOICES = [
        ('qa', 'QA'),
        ('stage', 'Staging'),
        ('prod', 'Production'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='environments')
    name = models.CharField(max_length=20, choices=ENVIRONMENT_CHOICES)
    config = models.JSONField(default=dict, blank=True, help_text="Parsed deploy-{env}.yaml content")
    secrets = EncryptedJSONField(default=dict, blank=True, help_text="Environment-specific secrets")
    active = models.BooleanField(default=True)
    domain = models.CharField(max_length=255, blank=True, help_text="Domain for this environment")
    ssl_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'deployer_environments'
        unique_together = ['project', 'name']
        ordering = ['project', 'name']
    
    def __str__(self):
        return f"{self.project.name}-{self.name}"
    
    def get_deployment_path(self):
        """Get the deployment path for this environment"""
        from django.conf import settings
        return os.path.join(settings.APPS_DIR, self.project.name, 'releases', self.name)
    
    def get_venv_path(self):
        """Get the virtual environment path"""
        from django.conf import settings
        return os.path.join(settings.APPS_DIR, self.project.name, 'envs', self.name)
    
    def get_current_deployment(self):
        """Get the currently active deployment"""
        return self.deployments.filter(status='active').first()


class Deployment(models.Model):
    """Deployment record"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('cloning', 'Cloning Repository'),
        ('building', 'Building'),
        ('deploying', 'Deploying'),
        ('testing', 'Running Tests'),
        ('active', 'Active'),
        ('failed', 'Failed'),
        ('rolled_back', 'Rolled Back'),
    ]
    
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, related_name='deployments')
    version = models.CharField(max_length=50)
    commit_sha = models.CharField(max_length=40)
    commit_message = models.TextField(blank=True)
    commit_author = models.CharField(max_length=100, blank=True)
    commit_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    deployment_path = models.CharField(max_length=255)
    deployed_by = models.CharField(max_length=100)
    deployed_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    rollback_from = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='rollbacks')
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'deployer_deployments'
        ordering = ['-deployed_at']
        indexes = [
            models.Index(fields=['-deployed_at']),
            models.Index(fields=['environment', 'status']),
        ]
    
    def __str__(self):
        return f"{self.environment} - {self.version} ({self.status})"
    
    def save(self, *args, **kwargs):
        """Override save to trigger deployment processing"""
        is_new = self.pk is None
        old_status = None
        
        if not is_new:
            # Get the old status if updating
            old_obj = Deployment.objects.filter(pk=self.pk).first()
            if old_obj:
                old_status = old_obj.status
        
        # Save the deployment
        super().save(*args, **kwargs)
        
        # Trigger async processing if this is a new deployment or status changed to pending
        if (is_new and self.status == 'pending') or (old_status != 'pending' and self.status == 'pending'):
            from deployer.tasks import process_deployment
            process_deployment.delay(self.id)
    
    def mark_active(self):
        """Mark this deployment as active and deactivate others"""
        # Deactivate other deployments
        self.environment.deployments.filter(status='active').update(status='inactive')
        self.status = 'active'
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self, error_message):
        """Mark deployment as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save()


class Service(models.Model):
    """Service instance for an environment"""
    SERVICE_TYPES = [
        ('django', 'Django Web'),
        ('celery', 'Celery Worker'),
        ('celery-beat', 'Celery Beat'),
        ('custom', 'Custom Service'),
    ]
    
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('stopped', 'Stopped'),
        ('failed', 'Failed'),
        ('restarting', 'Restarting'),
        ('unknown', 'Unknown'),
    ]
    
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=100)
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES)
    command = models.TextField()
    port = models.IntegerField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown')
    pid = models.IntegerField(null=True, blank=True)
    memory_usage = models.BigIntegerField(default=0, help_text="Memory usage in bytes")
    cpu_usage = models.FloatField(default=0.0, help_text="CPU usage percentage")
    last_health_check = models.DateTimeField(null=True, blank=True)
    health_check_endpoint = models.CharField(max_length=255, blank=True)
    supervisor_name = models.CharField(max_length=100, unique=True)
    enabled = models.BooleanField(default=True)
    max_memory = models.IntegerField(default=2048, help_text="Max memory in MB")
    max_cpu = models.FloatField(default=1.0, help_text="Max CPU cores")
    restart_count = models.IntegerField(default=0)
    last_restart = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'deployer_services'
        unique_together = ['environment', 'name']
        ordering = ['environment', 'name']
    
    def __str__(self):
        return f"{self.environment} - {self.name}"
    
    def get_supervisor_name(self):
        """Generate supervisor program name"""
        return f"{self.environment.project.name}-{self.environment.name}-{self.name}".replace('_', '-')


class DeploymentLog(models.Model):
    """Log entries for deployments"""
    LEVEL_CHOICES = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]
    
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='INFO')
    message = models.TextField()
    details = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'deployer_logs'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['deployment', 'timestamp']),
        ]
    
    def __str__(self):
        return f"[{self.level}] {self.deployment} - {self.message[:50]}"


class HealthCheck(models.Model):
    """Health check records for services"""
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='health_checks')
    timestamp = models.DateTimeField(auto_now_add=True)
    is_healthy = models.BooleanField()
    response_time = models.FloatField(null=True, blank=True, help_text="Response time in seconds")
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'deployer_health_checks'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['service', '-timestamp']),
        ]
    
    def __str__(self):
        status = "Healthy" if self.is_healthy else "Unhealthy"
        return f"{self.service} - {status} at {self.timestamp}"


class WebhookEvent(models.Model):
    """Track webhook events"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='webhook_events', null=True, blank=True)
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()
    headers = models.JSONField()
    processed = models.BooleanField(default=False)
    deployment = models.ForeignKey(Deployment, on_delete=models.SET_NULL, null=True, blank=True)
    error_message = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'deployer_webhook_events'
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['-received_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} for {self.project or 'Unknown'} at {self.received_at}"