import json
import hmac
import hashlib
import logging
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from core.models import Project, Environment, WebhookEvent
from deployer.executor import DeploymentExecutor

logger = logging.getLogger('deployer')


@method_decorator(csrf_exempt, name='dispatch')
class GitLabWebhookView(View):
    """Handle GitLab webhook events"""
    
    def post(self, request):
        """Process GitLab webhook"""
        try:
            # Get headers
            event_type = request.headers.get('X-Gitlab-Event', '')
            gitlab_token = request.headers.get('X-Gitlab-Token', '')
            
            # Parse payload
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON payload'}, status=400)
            
            # Extract project name from repository
            project_name = self._extract_project_name(payload)
            if not project_name:
                return JsonResponse({'error': 'Could not determine project name'}, status=400)
            
            # Find project
            try:
                project = Project.objects.get(name=project_name, active=True)
            except Project.DoesNotExist:
                logger.warning(f"Webhook received for unknown project: {project_name}")
                return JsonResponse({'error': f'Project {project_name} not found'}, status=404)
            
            # Verify webhook token
            if project.webhook_secret and gitlab_token != project.webhook_secret:
                logger.warning(f"Invalid webhook token for project {project_name}")
                return JsonResponse({'error': 'Invalid webhook token'}, status=401)
            
            # Create webhook event record
            webhook_event = WebhookEvent.objects.create(
                project=project,
                event_type=event_type,
                payload=payload,
                headers=dict(request.headers)
            )
            
            # Process based on event type
            if event_type == 'Push Hook':
                return self._handle_push_event(project, payload, webhook_event)
            elif event_type == 'Tag Push Hook':
                return self._handle_tag_event(project, payload, webhook_event)
            elif event_type == 'Merge Request Hook':
                return self._handle_merge_request_event(project, payload, webhook_event)
            elif event_type == 'Pipeline Hook':
                return self._handle_pipeline_event(project, payload, webhook_event)
            else:
                logger.info(f"Ignoring webhook event type: {event_type}")
                webhook_event.processed = True
                webhook_event.processed_at = timezone.now()
                webhook_event.save()
                return JsonResponse({'status': 'ignored', 'event': event_type})
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    def _extract_project_name(self, payload):
        """Extract project name from webhook payload"""
        # Try different locations in payload
        if 'project' in payload:
            # Try project.name first
            if 'name' in payload['project']:
                return payload['project']['name'].lower().replace(' ', '-')
            # Try project.path_with_namespace
            if 'path_with_namespace' in payload['project']:
                return payload['project']['path_with_namespace'].split('/')[-1]
        
        # Try repository.name
        if 'repository' in payload and 'name' in payload['repository']:
            return payload['repository']['name'].lower().replace(' ', '-')
        
        return None
    
    def _handle_push_event(self, project, payload, webhook_event):
        """Handle push events"""
        try:
            # Extract branch name
            ref = payload.get('ref', '')
            branch = ref.replace('refs/heads/', '') if ref.startswith('refs/heads/') else None
            
            if not branch:
                webhook_event.processed = True
                webhook_event.processed_at = timezone.now()
                webhook_event.save()
                return JsonResponse({'status': 'ignored', 'reason': 'Not a branch push'})
            
            # Determine environment based on branch
            environment_name = self._determine_environment(branch)
            if not environment_name:
                webhook_event.processed = True
                webhook_event.processed_at = timezone.now()
                webhook_event.save()
                return JsonResponse({
                    'status': 'ignored',
                    'reason': f'Branch {branch} not configured for auto-deployment'
                })
            
            # Check if environment exists and is active
            try:
                environment = project.environments.get(name=environment_name, active=True)
            except Environment.DoesNotExist:
                webhook_event.processed = True
                webhook_event.error_message = f'Environment {environment_name} not found or not active'
                webhook_event.processed_at = timezone.now()
                webhook_event.save()
                return JsonResponse({
                    'error': f'Environment {environment_name} not configured for {project.name}'
                }, status=404)
            
            # Extract commit information
            commits = payload.get('commits', [])
            if not commits:
                webhook_event.processed = True
                webhook_event.processed_at = timezone.now()
                webhook_event.save()
                return JsonResponse({'status': 'ignored', 'reason': 'No commits in push'})
            
            latest_commit = commits[-1]  # Last commit in the push
            commit_sha = latest_commit.get('id')
            commit_message = latest_commit.get('message', '')
            commit_author = latest_commit.get('author', {}).get('name', 'Unknown')
            
            # Check for deployment in progress
            if environment.deployments.filter(
                status__in=['pending', 'cloning', 'building', 'deploying', 'testing']
            ).exists():
                webhook_event.processed = True
                webhook_event.error_message = 'Deployment already in progress'
                webhook_event.processed_at = timezone.now()
                webhook_event.save()
                return JsonResponse({
                    'error': 'Deployment already in progress for this environment'
                }, status=409)
            
            # Trigger deployment
            executor = DeploymentExecutor()
            deployment = executor.deploy(
                project_name=project.name,
                environment_name=environment_name,
                commit_sha=commit_sha,
                deployed_by=f"webhook:{commit_author}"
            )
            
            # Update webhook event
            webhook_event.deployment = deployment
            webhook_event.processed = True
            webhook_event.processed_at = timezone.now()
            webhook_event.save()
            
            return JsonResponse({
                'status': 'success',
                'deployment': {
                    'id': deployment.id,
                    'version': deployment.version,
                    'environment': environment_name,
                    'commit': commit_sha[:8]
                }
            })
            
        except Exception as e:
            webhook_event.error_message = str(e)
            webhook_event.processed = True
            webhook_event.processed_at = timezone.now()
            webhook_event.save()
            raise
    
    def _handle_tag_event(self, project, payload, webhook_event):
        """Handle tag push events"""
        # Extract tag name
        ref = payload.get('ref', '')
        tag = ref.replace('refs/tags/', '') if ref.startswith('refs/tags/') else None
        
        if not tag:
            webhook_event.processed = True
            webhook_event.processed_at = timezone.now()
            webhook_event.save()
            return JsonResponse({'status': 'ignored', 'reason': 'Not a tag push'})
        
        # Tags could trigger production deployments
        # Implement your tag deployment logic here
        webhook_event.processed = True
        webhook_event.processed_at = timezone.now()
        webhook_event.save()
        
        logger.info(f"Tag {tag} pushed for project {project.name}")
        return JsonResponse({
            'status': 'acknowledged',
            'tag': tag,
            'message': 'Tag deployment not configured'
        })
    
    def _handle_merge_request_event(self, project, payload, webhook_event):
        """Handle merge request events"""
        # Could trigger deployments on merge to specific branches
        action = payload.get('object_attributes', {}).get('action')
        state = payload.get('object_attributes', {}).get('state')
        target_branch = payload.get('object_attributes', {}).get('target_branch')
        
        webhook_event.processed = True
        webhook_event.processed_at = timezone.now()
        webhook_event.save()
        
        logger.info(f"Merge request {action} for project {project.name}, target: {target_branch}")
        return JsonResponse({
            'status': 'acknowledged',
            'action': action,
            'state': state,
            'target_branch': target_branch
        })
    
    def _handle_pipeline_event(self, project, payload, webhook_event):
        """Handle pipeline events"""
        # Could trigger deployments on successful pipelines
        status = payload.get('object_attributes', {}).get('status')
        ref = payload.get('object_attributes', {}).get('ref')
        
        webhook_event.processed = True
        webhook_event.processed_at = timezone.now()
        webhook_event.save()
        
        logger.info(f"Pipeline {status} for project {project.name}, ref: {ref}")
        return JsonResponse({
            'status': 'acknowledged',
            'pipeline_status': status,
            'ref': ref
        })
    
    def _determine_environment(self, branch):
        """Determine environment based on branch name"""
        # Map branches to environments
        branch_mapping = {
            'develop': 'qa',
            'qa': 'qa',
            'staging': 'stage',
            'stage': 'stage',
            'master': 'prod',
            'main': 'prod',
            'production': 'prod',
        }
        
        return branch_mapping.get(branch.lower())


@method_decorator(csrf_exempt, name='dispatch')
class GenericWebhookView(View):
    """Generic webhook handler for custom integrations"""
    
    def post(self, request):
        """Process generic webhook"""
        try:
            # Get authentication token
            auth_token = request.headers.get('Authorization', '').replace('Bearer ', '')
            
            # Verify token (implement your auth logic)
            if not auth_token:
                return JsonResponse({'error': 'Missing authorization token'}, status=401)
            
            # Parse payload
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON payload'}, status=400)
            
            # Extract required fields
            project_name = payload.get('project')
            environment_name = payload.get('environment')
            action = payload.get('action', 'deploy')
            
            if not project_name or not environment_name:
                return JsonResponse({
                    'error': 'Missing required fields: project, environment'
                }, status=400)
            
            # Find project
            try:
                project = Project.objects.get(name=project_name, active=True)
            except Project.DoesNotExist:
                return JsonResponse({'error': f'Project {project_name} not found'}, status=404)
            
            # Create webhook event
            webhook_event = WebhookEvent.objects.create(
                project=project,
                event_type='generic',
                payload=payload,
                headers=dict(request.headers)
            )
            
            if action == 'deploy':
                # Trigger deployment
                try:
                    environment = project.environments.get(name=environment_name, active=True)
                    
                    executor = DeploymentExecutor()
                    deployment = executor.deploy(
                        project_name=project_name,
                        environment_name=environment_name,
                        commit_sha=payload.get('commit_sha'),
                        deployed_by=payload.get('deployed_by', 'webhook')
                    )
                    
                    webhook_event.deployment = deployment
                    webhook_event.processed = True
                    webhook_event.processed_at = timezone.now()
                    webhook_event.save()
                    
                    return JsonResponse({
                        'status': 'success',
                        'deployment_id': deployment.id,
                        'version': deployment.version
                    })
                    
                except Environment.DoesNotExist:
                    return JsonResponse({
                        'error': f'Environment {environment_name} not found'
                    }, status=404)
                except Exception as e:
                    webhook_event.error_message = str(e)
                    webhook_event.processed = True
                    webhook_event.processed_at = timezone.now()
                    webhook_event.save()
                    return JsonResponse({'error': str(e)}, status=500)
            
            elif action == 'rollback':
                # Trigger rollback
                try:
                    executor = DeploymentExecutor()
                    deployment = executor.rollback(
                        project_name=project_name,
                        environment_name=environment_name,
                        deployed_by=payload.get('deployed_by', 'webhook')
                    )
                    
                    webhook_event.deployment = deployment
                    webhook_event.processed = True
                    webhook_event.processed_at = timezone.now()
                    webhook_event.save()
                    
                    return JsonResponse({
                        'status': 'success',
                        'deployment_id': deployment.id,
                        'action': 'rollback'
                    })
                    
                except Exception as e:
                    webhook_event.error_message = str(e)
                    webhook_event.processed = True
                    webhook_event.processed_at = timezone.now()
                    webhook_event.save()
                    return JsonResponse({'error': str(e)}, status=500)
            
            else:
                webhook_event.processed = True
                webhook_event.processed_at = timezone.now()
                webhook_event.save()
                return JsonResponse({'error': f'Unknown action: {action}'}, status=400)
                
        except Exception as e:
            logger.error(f"Generic webhook failed: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)