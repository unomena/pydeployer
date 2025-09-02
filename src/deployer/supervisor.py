import os
import subprocess
import logging
from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger('deployer')


class SupervisorManager:
    """Manage Supervisor configurations and services"""
    
    def create_config(self, service, deployment, env_vars):
        """Create supervisor configuration for a service"""
        try:
            # Prepare context for template
            context = {
                'program_name': service.supervisor_name,
                'command': self._prepare_command(service, deployment, env_vars),
                'directory': self._get_working_directory(deployment),
                'user': settings.DEPLOYMENT_USER,
                'environment': self._format_environment(env_vars),
                'stdout_logfile': self._get_log_file(service, 'stdout'),
                'stderr_logfile': self._get_log_file(service, 'stderr'),
                'autostart': 'true',
                'autorestart': 'true',
                'startsecs': 10,
                'stopwaitsecs': 30,
                'killasgroup': 'true',
                'stopasgroup': 'true',
            }
            
            # Add service-specific settings
            if service.service_type == 'celery-beat':
                # Only one beat instance should run
                context['numprocs'] = 1
            elif service.service_type == 'celery':
                # Can have multiple worker processes
                context['numprocs'] = 1  # Can be configured per service
            
            # Generate configuration
            config_content = self._generate_config(context)
            
            # Write configuration file
            config_path = os.path.join(
                settings.SUPERVISOR_CONFIG_DIR,
                f"{service.supervisor_name}.conf"
            )
            
            os.makedirs(settings.SUPERVISOR_CONFIG_DIR, exist_ok=True)
            
            with open(config_path, 'w') as f:
                f.write(config_content)
            
            logger.info(f"Created supervisor config for {service.supervisor_name}")
            
            # Reload supervisor configuration
            self.reload_config()
            
        except Exception as e:
            logger.error(f"Failed to create supervisor config: {str(e)}")
            raise
    
    def _prepare_command(self, service, deployment, env_vars):
        """Prepare the command with proper paths"""
        command = service.command
        venv_path = os.path.join(
            settings.APPS_DIR,
            deployment.environment.project.name,
            'envs',
            deployment.environment.name
        )
        
        # Replace placeholders
        replacements = {
            '${PORT}': str(env_vars.get('PORT', '8000')),
            '${QUEUE_NAME}': f"{deployment.environment.project.name}-{deployment.environment.name}",
            '${PROJECT_NAME}': deployment.environment.project.name,
            '${ENVIRONMENT}': deployment.environment.name,
        }
        
        for placeholder, value in replacements.items():
            command = command.replace(placeholder, value)
        
        # Prepend virtual environment Python if needed
        if 'python' in command or 'gunicorn' in command or 'celery' in command:
            # Check if command starts with these executables
            executables = ['python', 'gunicorn', 'celery', 'django-admin', 'uwsgi']
            for exe in executables:
                if command.startswith(exe):
                    command = f"{os.path.join(venv_path, 'bin', exe)} {command[len(exe):].strip()}"
                    break
                elif f" {exe} " in command or command.endswith(f" {exe}"):
                    command = command.replace(exe, os.path.join(venv_path, 'bin', exe))
        
        return command
    
    def _get_working_directory(self, deployment):
        """Get working directory for the service"""
        # Always prefer src directory if it exists (standard project structure)
        src_path = os.path.join(deployment.deployment_path, 'src')
        if os.path.exists(src_path):
            return src_path
        return deployment.deployment_path
    
    def _format_environment(self, env_vars):
        """Format environment variables for supervisor"""
        env_list = []
        for key, value in env_vars.items():
            # Escape quotes in values
            value = str(value).replace('"', '\\"')
            env_list.append(f'{key}="{value}"')
        return ','.join(env_list)
    
    def _get_log_file(self, service, log_type):
        """Get log file path for service"""
        log_dir = os.path.join(
            settings.APPS_DIR,
            service.environment.project.name,
            'logs',
            service.environment.name
        )
        os.makedirs(log_dir, exist_ok=True)
        
        return os.path.join(log_dir, f"{service.name}_{log_type}.log")
    
    def _generate_config(self, context):
        """Generate supervisor configuration content"""
        template = """[program:{program_name}]
command={command}
directory={directory}
user={user}
autostart={autostart}
autorestart={autorestart}
startsecs={startsecs}
stopwaitsecs={stopwaitsecs}
killasgroup={killasgroup}
stopasgroup={stopasgroup}
stdout_logfile={stdout_logfile}
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
stderr_logfile={stderr_logfile}
stderr_logfile_maxbytes=10MB
stderr_logfile_backups=5
environment={environment}
"""
        return template.format(**context)
    
    def reload_config(self):
        """Reload supervisor configuration"""
        try:
            subprocess.run(['supervisorctl', 'reread'], check=True, capture_output=True)
            subprocess.run(['supervisorctl', 'update'], check=True, capture_output=True)
            logger.info("Supervisor configuration reloaded")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reload supervisor config: {e.stderr}")
            raise
    
    def reload_service(self, service_name):
        """Reload a specific service"""
        try:
            # Try graceful restart first
            result = subprocess.run(
                ['supervisorctl', 'restart', service_name],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                # If restart fails, try stop and start
                subprocess.run(['supervisorctl', 'stop', service_name], check=False)
                subprocess.run(['supervisorctl', 'start', service_name], check=True)
            
            logger.info(f"Reloaded service {service_name}")
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout reloading service {service_name}")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reload service {service_name}: {e.stderr}")
            raise
    
    def start_service(self, service_name):
        """Start a service"""
        try:
            subprocess.run(['supervisorctl', 'start', service_name], check=True, capture_output=True)
            logger.info(f"Started service {service_name}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start service {service_name}: {e.stderr}")
            raise
    
    def stop_service(self, service_name):
        """Stop a service"""
        try:
            subprocess.run(['supervisorctl', 'stop', service_name], check=True, capture_output=True)
            logger.info(f"Stopped service {service_name}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop service {service_name}: {e.stderr}")
            raise
    
    def get_service_status(self, service_name):
        """Get status of a service"""
        try:
            result = subprocess.run(
                ['supervisorctl', 'status', service_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Parse status output
                status_line = result.stdout.strip()
                if 'RUNNING' in status_line:
                    return 'running'
                elif 'STOPPED' in status_line:
                    return 'stopped'
                elif 'STARTING' in status_line:
                    return 'starting'
                elif 'FATAL' in status_line:
                    return 'failed'
                else:
                    return 'unknown'
            
            return 'unknown'
            
        except Exception as e:
            logger.error(f"Failed to get service status: {str(e)}")
            return 'unknown'
    
    def remove_config(self, service_name):
        """Remove supervisor configuration for a service"""
        try:
            config_path = os.path.join(
                settings.SUPERVISOR_CONFIG_DIR,
                f"{service_name}.conf"
            )
            
            if os.path.exists(config_path):
                # Stop service first
                try:
                    self.stop_service(service_name)
                except:
                    pass  # Service might not be running
                
                # Remove config file
                os.remove(config_path)
                
                # Reload supervisor
                self.reload_config()
                
                logger.info(f"Removed supervisor config for {service_name}")
                
        except Exception as e:
            logger.error(f"Failed to remove supervisor config: {str(e)}")
            raise