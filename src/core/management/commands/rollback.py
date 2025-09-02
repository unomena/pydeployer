from django.core.management.base import BaseCommand, CommandError
from core.models import Project, Environment
from deployer.executor import DeploymentExecutor
import logging

logger = logging.getLogger('deployer')


class Command(BaseCommand):
    help = 'Rollback a project to previous deployment'
    
    def add_arguments(self, parser):
        parser.add_argument('project', type=str, help='Project name')
        parser.add_argument(
            '--env',
            type=str,
            required=True,
            choices=['qa', 'stage', 'prod'],
            help='Environment to rollback'
        )
        parser.add_argument(
            '--deployed-by',
            type=str,
            default='cli',
            help='Who is performing rollback (default: cli)'
        )
    
    def handle(self, *args, **options):
        project_name = options['project']
        environment_name = options['env']
        deployed_by = options.get('deployed_by')
        
        try:
            # Verify project exists
            project = Project.objects.get(name=project_name, active=True)
            
            # Verify environment exists
            environment = project.environments.get(name=environment_name, active=True)
            
            # Check current deployment
            current = environment.deployments.filter(status='active').first()
            if not current:
                raise CommandError(
                    f'No active deployment found for {project_name}-{environment_name}'
                )
            
            # Check for previous deployment
            previous = environment.deployments.filter(
                status='inactive',
                completed_at__isnull=False
            ).order_by('-completed_at').first()
            
            if not previous:
                raise CommandError(
                    f'No previous deployment to rollback to for {project_name}-{environment_name}'
                )
            
            self.stdout.write(
                self.style.WARNING(
                    f'Rolling back {project_name}-{environment_name} '
                    f'from {current.version} to {previous.version}...'
                )
            )
            
            # Execute rollback
            executor = DeploymentExecutor()
            deployment = executor.rollback(
                project_name=project_name,
                environment_name=environment_name,
                deployed_by=deployed_by
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully rolled back {project_name}-{environment_name}\n'
                    f'Now running version: {previous.version}\n'
                    f'Rolled back from: {current.version}'
                )
            )
            
        except Project.DoesNotExist:
            raise CommandError(f'Project "{project_name}" does not exist or is not active')
        except Environment.DoesNotExist:
            raise CommandError(
                f'Environment "{environment_name}" does not exist for project "{project_name}"'
            )
        except Exception as e:
            logger.error(f'Rollback failed: {str(e)}')
            raise CommandError(f'Rollback failed: {str(e)}')