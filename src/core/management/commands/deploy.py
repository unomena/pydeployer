from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from core.models import Project, Environment
from deployer.executor import DeploymentExecutor
import logging

logger = logging.getLogger('deployer')


class Command(BaseCommand):
    help = 'Deploy a project to specified environment'
    
    def add_arguments(self, parser):
        parser.add_argument('project', type=str, help='Project name')
        parser.add_argument(
            '--env',
            type=str,
            required=True,
            choices=['qa', 'stage', 'prod'],
            help='Environment to deploy to'
        )
        parser.add_argument(
            '--commit',
            type=str,
            help='Specific commit SHA to deploy (optional)'
        )
        parser.add_argument(
            '--deployed-by',
            type=str,
            default='cli',
            help='Who is deploying (default: cli)'
        )
    
    def handle(self, *args, **options):
        project_name = options['project']
        environment_name = options['env']
        commit_sha = options.get('commit')
        deployed_by = options.get('deployed_by')
        
        try:
            # Verify project exists
            project = Project.objects.get(name=project_name, active=True)
            
            # Verify environment exists
            environment = project.environments.get(name=environment_name, active=True)
            
            self.stdout.write(
                self.style.WARNING(
                    f'Starting deployment of {project_name} to {environment_name}...'
                )
            )
            
            # Check for existing deployment in progress
            if environment.deployments.filter(
                status__in=['pending', 'cloning', 'building', 'deploying', 'testing']
            ).exists():
                raise CommandError(
                    f'Deployment already in progress for {project_name}-{environment_name}'
                )
            
            # Execute deployment
            executor = DeploymentExecutor()
            deployment = executor.deploy(
                project_name=project_name,
                environment_name=environment_name,
                commit_sha=commit_sha,
                deployed_by=deployed_by
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deployed {project_name} to {environment_name}\n'
                    f'Version: {deployment.version}\n'
                    f'Commit: {deployment.commit_sha[:8]}\n'
                    f'Status: {deployment.status}'
                )
            )
            
        except Project.DoesNotExist:
            raise CommandError(f'Project "{project_name}" does not exist or is not active')
        except Environment.DoesNotExist:
            raise CommandError(
                f'Environment "{environment_name}" does not exist for project "{project_name}"'
            )
        except Exception as e:
            logger.error(f'Deployment failed: {str(e)}')
            raise CommandError(f'Deployment failed: {str(e)}')