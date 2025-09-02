from django.core.management.base import BaseCommand
from core.models import Project, Environment, Deployment, Service


class Command(BaseCommand):
    help = 'Deregister a project and remove all related data'

    def add_arguments(self, parser):
        parser.add_argument('name', type=str, help='Project name to deregister')
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt'
        )

    def handle(self, *args, **options):
        project_name = options['name']
        force = options.get('force', False)
        
        try:
            project = Project.objects.get(name=project_name)
            
            # Count related objects
            env_count = project.environments.count()
            deployment_count = Deployment.objects.filter(environment__project=project).count()
            service_count = Service.objects.filter(environment__project=project).count()
            
            self.stdout.write(
                self.style.WARNING(
                    f'\nProject: {project_name}\n'
                    f'  - Environments: {env_count}\n'
                    f'  - Deployments: {deployment_count}\n'
                    f'  - Services: {service_count}\n'
                )
            )
            
            if not force:
                confirm = input(f'Are you sure you want to deregister "{project_name}" and delete all related data? (yes/no): ')
                if confirm.lower() != 'yes':
                    self.stdout.write(self.style.WARNING('Aborted'))
                    return
            
            # Delete the project (cascade will handle related objects)
            project.delete()
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deregistered project "{project_name}"')
            )
            
        except Project.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Project "{project_name}" not found')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error deregistering project: {e}')
            )