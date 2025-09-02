from django.core.management.base import BaseCommand, CommandError
from core.models import Project, Environment
import secrets


class Command(BaseCommand):
    help = 'Register a new project for deployment'
    
    def add_arguments(self, parser):
        parser.add_argument('name', type=str, help='Project name')
        parser.add_argument('--repo', type=str, required=True, help='Git repository URL')
        parser.add_argument(
            '--port-start',
            type=int,
            required=True,
            help='Starting port for service allocation'
        )
        parser.add_argument(
            '--branch',
            type=str,
            default='main',
            help='Default branch (default: main)'
        )
        parser.add_argument(
            '--deploy-key',
            type=str,
            help='SSH deploy key for private repositories'
        )
        parser.add_argument(
            '--description',
            type=str,
            help='Project description'
        )
        parser.add_argument(
            '--environments',
            type=str,
            default='qa,stage,prod',
            help='Comma-separated list of environments (default: qa,stage,prod)'
        )
    
    def handle(self, *args, **options):
        project_name = options['name']
        
        # Check if project already exists
        if Project.objects.filter(name=project_name).exists():
            raise CommandError(f'Project "{project_name}" already exists')
        
        try:
            # Create project
            project = Project.objects.create(
                name=project_name,
                repository_url=options['repo'],
                port_start=options['port_start'],
                default_branch=options.get('branch', 'main'),
                deploy_key=options.get('deploy_key', ''),
                description=options.get('description', ''),
                webhook_secret=secrets.token_urlsafe(32)
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Created project "{project_name}"')
            )
            
            # Create environments
            environments = options.get('environments', 'qa,stage,prod').split(',')
            for env_name in environments:
                env_name = env_name.strip()
                if env_name in ['qa', 'stage', 'prod']:
                    Environment.objects.create(
                        project=project,
                        name=env_name
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f'  Created environment "{env_name}"')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  Skipped invalid environment "{env_name}" '
                            f'(must be qa, stage, or prod)'
                        )
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nProject registered successfully!\n'
                    f'Name: {project.name}\n'
                    f'Repository: {project.repository_url}\n'
                    f'Port range: {project.port_start}+\n'
                    f'Webhook secret: {project.webhook_secret}\n'
                    f'Environments: {", ".join(environments)}'
                )
            )
            
            # Clone repository
            self.stdout.write(
                self.style.WARNING('\nCloning repository...')
            )
            
            from deployer.git_manager import GitManager
            git_manager = GitManager()
            repo_path = f"/opt/deployments/repos/{project.name}"
            
            try:
                git_manager.clone(
                    project.repository_url,
                    repo_path,
                    project.deploy_key if project.deploy_key else None
                )
                self.stdout.write(
                    self.style.SUCCESS('Repository cloned successfully!')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(
                        f'Failed to clone repository: {str(e)}\n'
                        f'You may need to clone it manually or fix the repository URL.'
                    )
                )
            
        except Exception as e:
            raise CommandError(f'Failed to register project: {str(e)}')