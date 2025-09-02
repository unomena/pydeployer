from django.core.management.base import BaseCommand
from core.models import Project, Environment
import secrets
import os


class Command(BaseCommand):
    help = 'Register PyDeployer to manage itself'
    
    def handle(self, *args, **options):
        project_name = 'pydeployer'
        
        # Check if already registered
        if Project.objects.filter(name=project_name).exists():
            self.stdout.write(
                self.style.WARNING(f'Project "{project_name}" is already registered')
            )
            return
        
        try:
            # Create project for self-management
            project = Project.objects.create(
                name=project_name,
                repository_url=os.environ.get(
                    'PYDEPLOYER_REPO',
                    'https://gitlab.com/company/pydeployer.git'
                ),
                port_start=8000,
                default_branch='main',
                description='PyDeployer - Self-managed deployment system',
                webhook_secret=secrets.token_urlsafe(32),
                active=True
            )
            
            # Create production environment only (pydeployer typically runs in prod)
            Environment.objects.create(
                project=project,
                name='prod',
                config={
                    'name': 'pydeployer',
                    'python_version': '3.11',
                    'requirements': 'requirements.txt',
                    'services': [
                        {
                            'name': 'web',
                            'type': 'django',
                            'command': 'gunicorn --bind 127.0.0.1:${PORT} --workers=2 --threads=4 --worker-class=gthread pydeployer.wsgi',
                            'enabled': True,
                            'health_check': {
                                'endpoint': '/api/status/',
                                'interval': 60
                            },
                            'resources': {
                                'max_memory': 1024,
                                'max_cpu': 0.5
                            }
                        }
                    ],
                    'env_vars': {
                        'DJANGO_SETTINGS_MODULE': 'pydeployer.settings',
                        'PYTHONUNBUFFERED': '1',
                        'DEBUG': '0'
                    },
                    'hooks': {
                        'pre_deploy': [
                            'python manage.py migrate --noinput',
                            'python manage.py collectstatic --noinput'
                        ],
                        'post_deploy': [
                            'python manage.py check --deploy'
                        ]
                    }
                },
                active=True
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully registered PyDeployer for self-management!\n'
                    f'Project: {project.name}\n'
                    f'Port: {project.port_start}\n'
                    f'Webhook secret: {project.webhook_secret}\n\n'
                    f'PyDeployer can now deploy itself using:\n'
                    f'  python manage.py deploy pydeployer --env=prod\n\n'
                    f'Note: The first deployment must be done manually.'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to register PyDeployer: {str(e)}')
            )