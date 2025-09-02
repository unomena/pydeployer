from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    Project, Environment, Deployment, Service, 
    DeploymentLog, HealthCheck, WebhookEvent
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'repository_url', 'port_start', 'active', 'created_at']
    list_filter = ['active', 'created_at']
    search_fields = ['name', 'repository_url', 'description']
    readonly_fields = ['created_at', 'updated_at', 'webhook_secret']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'active')
        }),
        ('Repository', {
            'fields': ('repository_url', 'default_branch', 'deploy_key')
        }),
        ('Configuration', {
            'fields': ('port_start', 'webhook_secret')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.webhook_secret:
            import secrets
            obj.webhook_secret = secrets.token_urlsafe(32)
        super().save_model(request, obj, form, change)


@admin.register(Environment)
class EnvironmentAdmin(admin.ModelAdmin):
    list_display = ['project', 'name', 'active', 'domain', 'ssl_enabled', 'current_deployment_status']
    list_filter = ['name', 'active', 'ssl_enabled', 'project']
    search_fields = ['project__name', 'domain']
    readonly_fields = ['created_at', 'updated_at', 'get_deployment_path', 'get_venv_path']
    
    fieldsets = (
        (None, {
            'fields': ('project', 'name', 'active')
        }),
        ('Configuration', {
            'fields': ('config', 'secrets', 'domain', 'ssl_enabled')
        }),
        ('Paths', {
            'fields': ('get_deployment_path', 'get_venv_path'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def current_deployment_status(self, obj):
        deployment = obj.get_current_deployment()
        if deployment:
            color = {
                'active': 'green',
                'deploying': 'orange',
                'failed': 'red',
                'rolled_back': 'gray',
            }.get(deployment.status, 'black')
            return format_html(
                '<span style="color: {};">{}</span>',
                color,
                deployment.status.upper()
            )
        return '-'
    current_deployment_status.short_description = 'Current Status'


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin):
    list_display = ['environment', 'version', 'status_colored', 'deployed_by', 'deployed_at', 'completed_at']
    list_filter = ['status', 'environment__project', 'environment__name', 'deployed_at']
    search_fields = ['version', 'commit_sha', 'commit_message', 'deployed_by']
    readonly_fields = ['deployed_at', 'completed_at', 'deployment_path']
    date_hierarchy = 'deployed_at'
    
    fieldsets = (
        (None, {
            'fields': ('environment', 'status', 'version')
        }),
        ('Commit Information', {
            'fields': ('commit_sha', 'commit_message', 'commit_author', 'commit_date')
        }),
        ('Deployment Details', {
            'fields': ('deployed_by', 'deployment_path', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('deployed_at', 'completed_at')
        }),
        ('Rollback', {
            'fields': ('rollback_from',),
            'classes': ('collapse',)
        }),
    )
    
    def status_colored(self, obj):
        colors = {
            'pending': '#FFA500',
            'cloning': '#1E90FF',
            'building': '#1E90FF',
            'deploying': '#1E90FF',
            'testing': '#1E90FF',
            'active': '#008000',
            'failed': '#FF0000',
            'rolled_back': '#808080',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#000000'),
            obj.status.upper()
        )
    status_colored.short_description = 'Status'
    
    actions = ['mark_as_active', 'rollback_deployment']
    
    def mark_as_active(self, request, queryset):
        for deployment in queryset:
            deployment.mark_active()
        self.message_user(request, f"{queryset.count()} deployment(s) marked as active.")
    mark_as_active.short_description = "Mark selected deployments as active"
    
    def rollback_deployment(self, request, queryset):
        for deployment in queryset:
            # Trigger rollback logic here
            pass
        self.message_user(request, f"Rollback initiated for {queryset.count()} deployment(s).")
    rollback_deployment.short_description = "Rollback selected deployments"


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['environment', 'name', 'service_type', 'status_colored', 'port', 'enabled', 'last_health_check']
    list_filter = ['service_type', 'status', 'enabled', 'environment__project', 'environment__name']
    search_fields = ['name', 'supervisor_name', 'command']
    readonly_fields = ['supervisor_name', 'pid', 'memory_usage', 'cpu_usage', 'last_health_check', 'restart_count', 'last_restart']
    
    fieldsets = (
        (None, {
            'fields': ('environment', 'name', 'service_type', 'enabled')
        }),
        ('Configuration', {
            'fields': ('command', 'port', 'health_check_endpoint', 'supervisor_name')
        }),
        ('Resource Limits', {
            'fields': ('max_memory', 'max_cpu')
        }),
        ('Runtime Status', {
            'fields': ('status', 'pid', 'memory_usage', 'cpu_usage', 'last_health_check')
        }),
        ('Restart Information', {
            'fields': ('restart_count', 'last_restart'),
            'classes': ('collapse',)
        }),
    )
    
    def status_colored(self, obj):
        colors = {
            'running': 'green',
            'stopped': 'orange',
            'failed': 'red',
            'restarting': 'blue',
            'unknown': 'gray',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.status.upper()
        )
    status_colored.short_description = 'Status'
    
    actions = ['restart_service', 'stop_service', 'start_service']
    
    def restart_service(self, request, queryset):
        # Implement service restart logic
        self.message_user(request, f"Restarting {queryset.count()} service(s).")
    restart_service.short_description = "Restart selected services"
    
    def stop_service(self, request, queryset):
        # Implement service stop logic
        self.message_user(request, f"Stopping {queryset.count()} service(s).")
    stop_service.short_description = "Stop selected services"
    
    def start_service(self, request, queryset):
        # Implement service start logic
        self.message_user(request, f"Starting {queryset.count()} service(s).")
    start_service.short_description = "Start selected services"


@admin.register(DeploymentLog)
class DeploymentLogAdmin(admin.ModelAdmin):
    list_display = ['deployment', 'timestamp', 'level_colored', 'message_truncated']
    list_filter = ['level', 'deployment__environment__project', 'timestamp']
    search_fields = ['message', 'deployment__version']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def level_colored(self, obj):
        colors = {
            'DEBUG': 'gray',
            'INFO': 'blue',
            'WARNING': 'orange',
            'ERROR': 'red',
            'CRITICAL': 'darkred',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.level, 'black'),
            obj.level
        )
    level_colored.short_description = 'Level'
    
    def message_truncated(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_truncated.short_description = 'Message'


@admin.register(HealthCheck)
class HealthCheckAdmin(admin.ModelAdmin):
    list_display = ['service', 'timestamp', 'is_healthy_icon', 'response_time', 'error_message_truncated']
    list_filter = ['is_healthy', 'service__environment__project', 'timestamp']
    search_fields = ['service__name', 'error_message']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def is_healthy_icon(self, obj):
        if obj.is_healthy:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    is_healthy_icon.short_description = 'Healthy'
    
    def error_message_truncated(self, obj):
        if obj.error_message:
            return obj.error_message[:50] + '...' if len(obj.error_message) > 50 else obj.error_message
        return '-'
    error_message_truncated.short_description = 'Error'


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ['project', 'event_type', 'processed_icon', 'received_at', 'processed_at']
    list_filter = ['processed', 'event_type', 'project', 'received_at']
    search_fields = ['project__name', 'event_type', 'error_message']
    readonly_fields = ['received_at', 'processed_at', 'payload', 'headers']
    date_hierarchy = 'received_at'
    
    def processed_icon(self, obj):
        if obj.processed:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: orange;">⏳</span>')
    processed_icon.short_description = 'Processed'