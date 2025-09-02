from django.core.management.base import BaseCommand
from core.models import Deployment, Project


class Command(BaseCommand):
    help = 'Delete all deployment records for a project'

    def add_arguments(self, parser):
        parser.add_argument('project', type=str, help='Project name')
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt'
        )

    def handle(self, *args, **options):
        project_name = options['project']
        force = options.get('force', False)
        
        try:
            project = Project.objects.get(name=project_name)
            
            # Count deployments
            count = Deployment.objects.filter(environment__project=project).count()
            
            if count == 0:
                self.stdout.write(
                    self.style.WARNING(f'No deployments found for project {project_name}')
                )
                return
            
            if not force:
                confirm = input(f'Delete {count} deployments for {project_name}? (yes/no): ')
                if confirm.lower() != 'yes':
                    self.stdout.write(self.style.WARNING('Aborted'))
                    return
            
            # Delete deployments
            Deployment.objects.filter(environment__project=project).delete()
            
            self.stdout.write(
                self.style.SUCCESS(f'Deleted {count} deployments for {project_name}')
            )
            
        except Project.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Project {project_name} not found')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            )