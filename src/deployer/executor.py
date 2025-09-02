import os
import shutil
import subprocess
import logging
import yaml
import venv
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from core.models import (
    Project, Environment, Deployment, Service, 
    DeploymentLog, HealthCheck
)
from .git_manager import GitManager
from .venv_manager import VenvManager
from .supervisor import SupervisorManager
from .nginx import NginxManager

logger = logging.getLogger('deployer')


class DeploymentExecutor:
    """Main deployment orchestration class"""
    
    def __init__(self):
        self.git_manager = GitManager()
        self.venv_manager = VenvManager()
        self.supervisor_manager = SupervisorManager()
        self.nginx_manager = NginxManager()
    
    def deploy(self, project_name, environment_name, commit_sha=None, deployed_by='system'):
        """Execute a deployment"""
        try:
            # Get project and environment
            project = Project.objects.get(name=project_name, active=True)
            environment = project.environments.get(name=environment_name, active=True)
            
            # Create deployment record
            deployment = Deployment.objects.create(
                environment=environment,
                commit_sha=commit_sha or 'HEAD',
                status='pending',
                deployed_by=deployed_by,
                version=self._generate_version()
            )
            
            self._log(deployment, 'INFO', f'Starting deployment for {project_name}-{environment_name}')
            
            try:
                # Execute deployment steps
                self._clone_or_update_repo(project, deployment)
                self._checkout_commit(project, deployment, commit_sha)
                config = self._load_deployment_config(project, environment_name, deployment)
                self._create_release_directory(project, environment, deployment)
                self._setup_virtual_environment(project, environment, config, deployment)
                self._install_dependencies(project, environment, config, deployment)
                env_vars = self._prepare_environment_variables(environment, config, deployment)
                self._run_pre_deploy_hooks(config, deployment, env_vars)
                self._update_supervisor_configs(project, environment, config, deployment, env_vars)
                self._update_nginx_config(project, environment, config, deployment)
                self._switch_symlink(project, environment, deployment)
                self._reload_services(project, environment, deployment)
                self._perform_health_checks(environment, deployment)
                self._run_post_deploy_hooks(config, deployment, env_vars)
                self._cleanup_old_releases(project, environment, deployment)
                
                # Mark deployment as successful
                deployment.status = 'active'
                deployment.completed_at = timezone.now()
                deployment.save()
                
                # Deactivate previous deployments
                environment.deployments.exclude(id=deployment.id).filter(
                    status='active'
                ).update(status='inactive')
                
                self._log(deployment, 'INFO', 'Deployment completed successfully')
                return deployment
                
            except Exception as e:
                self._handle_deployment_failure(deployment, str(e))
                raise
                
        except Exception as e:
            logger.error(f"Deployment failed: {str(e)}")
            raise
    
    def rollback(self, project_name, environment_name, deployed_by='system'):
        """Rollback to previous deployment"""
        try:
            project = Project.objects.get(name=project_name)
            environment = project.environments.get(name=environment_name)
            
            # Get current and previous deployments
            current = environment.deployments.filter(status='active').first()
            if not current:
                raise ValueError("No active deployment to rollback")
            
            previous = environment.deployments.filter(
                status='inactive',
                completed_at__isnull=False
            ).order_by('-completed_at').first()
            
            if not previous:
                raise ValueError("No previous deployment to rollback to")
            
            # Create rollback deployment record
            rollback_deployment = Deployment.objects.create(
                environment=environment,
                commit_sha=previous.commit_sha,
                status='deploying',
                deployed_by=deployed_by,
                version=f"rollback-{self._generate_version()}",
                rollback_from=current
            )
            
            self._log(rollback_deployment, 'INFO', f'Rolling back from {current.version} to {previous.version}')
            
            # Switch symlink to previous release
            self._switch_symlink_to_release(project, environment, previous.deployment_path)
            
            # Reload services
            self._reload_services(project, environment, rollback_deployment)
            
            # Update deployment statuses
            current.status = 'rolled_back'
            current.save()
            
            previous.status = 'active'
            previous.save()
            
            rollback_deployment.status = 'active'
            rollback_deployment.completed_at = timezone.now()
            rollback_deployment.save()
            
            self._log(rollback_deployment, 'INFO', 'Rollback completed successfully')
            return rollback_deployment
            
        except Exception as e:
            logger.error(f"Rollback failed: {str(e)}")
            raise
    
    def _generate_version(self):
        """Generate version string based on timestamp"""
        return datetime.now().strftime("%Y%m%d-%H%M%S")
    
    def _log(self, deployment, level, message, details=None):
        """Log deployment message"""
        DeploymentLog.objects.create(
            deployment=deployment,
            level=level,
            message=message,
            details=details
        )
        logger.log(getattr(logging, level), f"[{deployment.id}] {message}")
    
    def _clone_or_update_repo(self, project, deployment):
        """Clone or update git repository"""
        deployment.status = 'cloning'
        deployment.save()
        
        self._log(deployment, 'INFO', 'Cloning/updating repository')
        
        repo_path = os.path.join(settings.REPOS_DIR, project.name)
        
        if not os.path.exists(repo_path):
            # Clone repository
            self.git_manager.clone(project.repository_url, repo_path, project.deploy_key)
        else:
            # Fetch latest changes
            self.git_manager.fetch(repo_path)
        
        self._log(deployment, 'INFO', 'Repository updated successfully')
    
    def _checkout_commit(self, project, deployment, commit_sha):
        """Checkout specific commit"""
        repo_path = os.path.join(settings.REPOS_DIR, project.name)
        
        if commit_sha:
            self.git_manager.checkout(repo_path, commit_sha)
            deployment.commit_sha = commit_sha
        else:
            # Get latest commit on default branch
            commit_sha = self.git_manager.get_latest_commit(repo_path, project.default_branch)
            self.git_manager.checkout(repo_path, commit_sha)
            deployment.commit_sha = commit_sha
        
        # Get commit info
        commit_info = self.git_manager.get_commit_info(repo_path, commit_sha)
        deployment.commit_message = commit_info.get('message', '')
        deployment.commit_author = commit_info.get('author', '')
        deployment.commit_date = commit_info.get('date')
        deployment.save()
        
        self._log(deployment, 'INFO', f'Checked out commit {commit_sha[:8]}')
    
    def _load_deployment_config(self, project, environment_name, deployment):
        """Load deployment configuration from yaml file"""
        deployment.status = 'building'
        deployment.save()
        
        repo_path = os.path.join(settings.REPOS_DIR, project.name)
        
        # Try environment-specific config first
        config_files = [
            f"deploy-{environment_name}.yaml",
            f"deploy-{environment_name}.yml",
            "deploy.yaml",
            "deploy.yml"
        ]
        
        config = None
        for config_file in config_files:
            config_path = os.path.join(repo_path, config_file)
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                self._log(deployment, 'INFO', f'Loaded configuration from {config_file}')
                break
        
        if not config:
            raise ValueError("No deployment configuration file found")
        
        # Validate required fields
        required_fields = ['name', 'services']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field in config: {field}")
        
        # Store config in environment
        environment = deployment.environment
        environment.config = config
        environment.save()
        
        return config
    
    def _create_release_directory(self, project, environment, deployment):
        """Create release directory"""
        repo_path = os.path.join(settings.REPOS_DIR, project.name)
        release_path = os.path.join(
            settings.APPS_DIR,
            project.name,
            'releases',
            environment.name,
            deployment.version
        )
        
        # Create directory structure
        os.makedirs(release_path, exist_ok=True)
        
        # Copy repository to release directory
        self._log(deployment, 'INFO', f'Creating release directory {release_path}')
        shutil.copytree(repo_path, release_path, dirs_exist_ok=True)
        
        deployment.deployment_path = release_path
        deployment.save()
        
        self._log(deployment, 'INFO', 'Release directory created')
    
    def _setup_virtual_environment(self, project, environment, config, deployment):
        """Setup or update virtual environment"""
        venv_path = os.path.join(settings.APPS_DIR, project.name, 'envs', environment.name)
        python_version = config.get('python_version', '3.11')
        
        if not os.path.exists(venv_path):
            self._log(deployment, 'INFO', f'Creating virtual environment with Python {python_version}')
            self.venv_manager.create(venv_path, python_version)
        else:
            self._log(deployment, 'INFO', 'Using existing virtual environment')
        
        self._log(deployment, 'INFO', 'Virtual environment ready')
    
    def _install_dependencies(self, project, environment, config, deployment):
        """Install Python dependencies"""
        venv_path = os.path.join(settings.APPS_DIR, project.name, 'envs', environment.name)
        requirements_file = config.get('requirements', 'requirements.txt')
        requirements_path = os.path.join(deployment.deployment_path, requirements_file)
        
        if os.path.exists(requirements_path):
            self._log(deployment, 'INFO', f'Installing dependencies from {requirements_file}')
            self.venv_manager.install_requirements(venv_path, requirements_path)
            self._log(deployment, 'INFO', 'Dependencies installed successfully')
        else:
            self._log(deployment, 'WARNING', f'Requirements file {requirements_file} not found')
    
    def _prepare_environment_variables(self, environment, config, deployment):
        """Prepare environment variables"""
        env_vars = {}
        
        # Add system environment variables
        env_vars['DEPLOYMENT_VERSION'] = deployment.version
        env_vars['DEPLOYMENT_ENV'] = environment.name
        env_vars['PROJECT_NAME'] = environment.project.name
        
        # Add config environment variables
        if 'env_vars' in config:
            for key, value in config['env_vars'].items():
                # Replace placeholders with secrets
                if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                    secret_key = value[2:-1]
                    if secret_key.startswith('SECRET_'):
                        secret_name = secret_key[7:]
                        if secret_name in environment.secrets:
                            value = environment.secrets[secret_name]
                env_vars[key] = str(value)
        
        # Add secrets directly
        for key, value in environment.secrets.items():
            if not key.startswith('_'):  # Skip internal keys
                env_vars[key] = str(value)
        
        self._log(deployment, 'INFO', f'Prepared {len(env_vars)} environment variables')
        return env_vars
    
    def _run_pre_deploy_hooks(self, config, deployment, env_vars):
        """Run pre-deployment hooks"""
        hooks = config.get('hooks', {}).get('pre_deploy', [])
        if hooks:
            deployment.status = 'deploying'
            deployment.save()
            self._log(deployment, 'INFO', f'Running {len(hooks)} pre-deploy hooks')
            
            for hook in hooks:
                self._run_hook(hook, deployment, env_vars)
    
    def _run_post_deploy_hooks(self, config, deployment, env_vars):
        """Run post-deployment hooks"""
        hooks = config.get('hooks', {}).get('post_deploy', [])
        if hooks:
            self._log(deployment, 'INFO', f'Running {len(hooks)} post-deploy hooks')
            
            for hook in hooks:
                self._run_hook(hook, deployment, env_vars)
    
    def _run_hook(self, command, deployment, env_vars):
        """Execute a hook command"""
        venv_path = os.path.join(
            settings.APPS_DIR,
            deployment.environment.project.name,
            'envs',
            deployment.environment.name
        )
        
        # Determine working directory - prefer src/ if it exists
        working_dir = deployment.deployment_path
        src_path = os.path.join(deployment.deployment_path, 'src')
        if os.path.exists(src_path):
            # If command starts with "cd src &&", remove it since we're already in src
            if command.startswith('cd src && '):
                command = command[10:]  # Remove "cd src && "
                working_dir = src_path
            elif not command.startswith('cd '):
                # If no cd command and src exists, use src as working dir
                working_dir = src_path
        
        # Prepare command with virtual environment
        if 'python ' in command or 'manage.py' in command:
            python_path = os.path.join(venv_path, 'bin', 'python')
            # Replace python with venv python
            command = command.replace('python ', f'{python_path} ')
            # Handle cases where python might not be at the start
            for py_cmd in ['gunicorn', 'celery', 'django-admin', 'uwsgi']:
                if py_cmd in command:
                    command = command.replace(py_cmd, os.path.join(venv_path, 'bin', py_cmd))
        
        self._log(deployment, 'INFO', f'Running hook: {command}')
        
        try:
            # Set up environment
            hook_env = os.environ.copy()
            hook_env.update(env_vars)
            hook_env['PATH'] = f"{os.path.join(venv_path, 'bin')}:{hook_env.get('PATH', '')}"
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                env=hook_env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Hook failed: {result.stderr}")
            
            self._log(deployment, 'INFO', f'Hook completed successfully')
            if result.stdout:
                self._log(deployment, 'DEBUG', f'Hook output: {result.stdout[:500]}')
                
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Hook timed out: {command}")
        except Exception as e:
            raise RuntimeError(f"Hook failed: {command} - {str(e)}")
    
    def _update_supervisor_configs(self, project, environment, config, deployment, env_vars):
        """Update supervisor configurations"""
        self._log(deployment, 'INFO', 'Updating supervisor configurations')
        
        services = config.get('services', [])
        for service_config in services:
            if not service_config.get('enabled', True):
                continue
            
            # Create or update service record
            service, created = Service.objects.update_or_create(
                environment=environment,
                name=service_config['name'],
                defaults={
                    'service_type': service_config['type'],
                    'command': service_config['command'],
                    'enabled': True,
                    'max_memory': service_config.get('resources', {}).get('max_memory', 2048),
                    'max_cpu': service_config.get('resources', {}).get('max_cpu', 1.0),
                }
            )
            
            # Assign port for web services
            if service.service_type == 'django' and not service.port:
                service.port = project.get_next_available_port(environment.name)
                service.save()
            
            # Update supervisor name
            service.supervisor_name = service.get_supervisor_name()
            service.save()
            
            # Generate supervisor config
            self.supervisor_manager.create_config(
                service=service,
                deployment=deployment,
                env_vars={**env_vars, 'PORT': str(service.port) if service.port else ''}
            )
        
        self._log(deployment, 'INFO', f'Updated {len(services)} supervisor configurations')
    
    def _update_nginx_config(self, project, environment, config, deployment):
        """Update nginx configuration for web services"""
        web_services = Service.objects.filter(
            environment=environment,
            service_type='django',
            enabled=True
        )
        
        if web_services.exists():
            self._log(deployment, 'INFO', 'Updating nginx configuration')
            self.nginx_manager.create_config(environment, list(web_services))
            self._log(deployment, 'INFO', 'Nginx configuration updated')
    
    def _switch_symlink(self, project, environment, deployment):
        """Switch current symlink to new release"""
        current_path = os.path.join(
            settings.APPS_DIR,
            project.name,
            'releases',
            environment.name,
            'current'
        )
        
        # Remove old symlink if exists
        if os.path.exists(current_path):
            os.unlink(current_path)
        
        # Create new symlink
        os.symlink(deployment.deployment_path, current_path)
        self._log(deployment, 'INFO', f'Switched symlink to {deployment.version}')
    
    def _switch_symlink_to_release(self, project, environment, release_path):
        """Switch symlink to specific release"""
        current_path = os.path.join(
            settings.APPS_DIR,
            project.name,
            'releases',
            environment.name,
            'current'
        )
        
        if os.path.exists(current_path):
            os.unlink(current_path)
        
        os.symlink(release_path, current_path)
    
    def _reload_services(self, project, environment, deployment):
        """Reload services via supervisor"""
        self._log(deployment, 'INFO', 'Reloading services')
        
        services = Service.objects.filter(environment=environment, enabled=True)
        for service in services:
            try:
                self.supervisor_manager.reload_service(service.supervisor_name)
                service.status = 'running'
                service.save()
                self._log(deployment, 'INFO', f'Reloaded service {service.name}')
            except Exception as e:
                self._log(deployment, 'ERROR', f'Failed to reload service {service.name}: {str(e)}')
                service.status = 'failed'
                service.save()
        
        # Reload nginx if web services exist
        if services.filter(service_type='django').exists():
            try:
                self.nginx_manager.reload()
                self._log(deployment, 'INFO', 'Reloaded nginx')
            except Exception as e:
                self._log(deployment, 'ERROR', f'Failed to reload nginx: {str(e)}')
    
    def _perform_health_checks(self, environment, deployment):
        """Perform health checks on services"""
        deployment.status = 'testing'
        deployment.save()
        
        self._log(deployment, 'INFO', 'Performing health checks')
        
        services = Service.objects.filter(environment=environment, enabled=True)
        all_healthy = True
        
        for service in services:
            if service.service_type == 'django' and service.health_check_endpoint:
                # Perform HTTP health check
                import requests
                try:
                    url = f"http://127.0.0.1:{service.port}{service.health_check_endpoint}"
                    response = requests.get(url, timeout=5)
                    is_healthy = response.status_code == 200
                    
                    HealthCheck.objects.create(
                        service=service,
                        is_healthy=is_healthy,
                        response_time=response.elapsed.total_seconds(),
                        error_message='' if is_healthy else f'Status code: {response.status_code}'
                    )
                    
                    if is_healthy:
                        self._log(deployment, 'INFO', f'Health check passed for {service.name}')
                    else:
                        self._log(deployment, 'ERROR', f'Health check failed for {service.name}')
                        all_healthy = False
                        
                except Exception as e:
                    HealthCheck.objects.create(
                        service=service,
                        is_healthy=False,
                        error_message=str(e)
                    )
                    self._log(deployment, 'ERROR', f'Health check failed for {service.name}: {str(e)}')
                    all_healthy = False
            
            service.last_health_check = timezone.now()
            service.save()
        
        if not all_healthy:
            raise RuntimeError("Health checks failed")
        
        self._log(deployment, 'INFO', 'All health checks passed')
    
    def _cleanup_old_releases(self, project, environment, deployment, keep=5):
        """Clean up old release directories"""
        releases_dir = os.path.join(
            settings.APPS_DIR,
            project.name,
            'releases',
            environment.name
        )
        
        if not os.path.exists(releases_dir):
            return
        
        # Get all release directories
        releases = []
        for item in os.listdir(releases_dir):
            if item == 'current':
                continue
            item_path = os.path.join(releases_dir, item)
            if os.path.isdir(item_path):
                releases.append((item, os.path.getctime(item_path)))
        
        # Sort by creation time
        releases.sort(key=lambda x: x[1], reverse=True)
        
        # Remove old releases
        if len(releases) > keep:
            for release, _ in releases[keep:]:
                release_path = os.path.join(releases_dir, release)
                try:
                    shutil.rmtree(release_path)
                    self._log(deployment, 'INFO', f'Removed old release {release}')
                except Exception as e:
                    self._log(deployment, 'WARNING', f'Failed to remove old release {release}: {str(e)}')
    
    def _handle_deployment_failure(self, deployment, error_message):
        """Handle deployment failure"""
        deployment.status = 'failed'
        deployment.error_message = error_message
        deployment.completed_at = timezone.now()
        deployment.save()
        
        self._log(deployment, 'ERROR', f'Deployment failed: {error_message}')
        
        # Attempt automatic rollback
        try:
            self._log(deployment, 'INFO', 'Attempting automatic rollback')
            self.rollback(
                deployment.environment.project.name,
                deployment.environment.name,
                deployed_by='auto-rollback'
            )
            self._log(deployment, 'INFO', 'Automatic rollback completed')
        except Exception as rollback_error:
            self._log(deployment, 'ERROR', f'Automatic rollback failed: {str(rollback_error)}')