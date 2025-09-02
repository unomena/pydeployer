from django.core.management.base import BaseCommand
from core.models import Deployment, Environment, Project


class Command(BaseCommand):
    help = 'Clean up stuck deployments by marking them as failed'

    def add_arguments(self, parser):
        parser.add_argument('project', type=str, help='Project name')
        parser.add_argument('environment', type=str, help='Environment name')

    def handle(self, *args, **options):
        project_name = options['project']
        env_name = options['environment']
        
        try:
            project = Project.objects.get(name=project_name)
            environment = Environment.objects.get(project=project, name=env_name)
            
            # Find stuck deployment
            deployment = environment.deployments.filter(
                status__in=['pending', 'cloning', 'building', 'deploying', 'testing']
            ).first()
            
            if deployment:
                deployment.status = 'failed'
                deployment.error_message = 'Manually cleaned up'
                deployment.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Deployment {deployment.id} marked as failed')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('No pending deployment found')
                )
                
        except Project.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Project {project_name} not found')
            )
        except Environment.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Environment {env_name} not found for project {project_name}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            )