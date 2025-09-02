import os
import subprocess
from datetime import datetime
from git import Repo
import logging

logger = logging.getLogger('deployer')


class GitManager:
    """Manage Git operations for deployments"""
    
    def clone(self, repo_url, target_path, deploy_key=None):
        """Clone a git repository"""
        try:
            # Setup SSH key if provided
            env = os.environ.copy()
            if deploy_key:
                # Write deploy key to temporary file
                key_file = f"/tmp/deploy_key_{os.getpid()}"
                with open(key_file, 'w') as f:
                    f.write(deploy_key)
                os.chmod(key_file, 0o600)
                
                # Set up SSH command
                env['GIT_SSH_COMMAND'] = f'ssh -i {key_file} -o StrictHostKeyChecking=no'
            
            # Clone repository
            logger.info(f"Cloning repository {repo_url} to {target_path}")
            
            if deploy_key:
                # Use subprocess for SSH key support
                result = subprocess.run(
                    ['git', 'clone', repo_url, target_path],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True
                )
            else:
                # Use GitPython for simplicity
                Repo.clone_from(repo_url, target_path)
            
            logger.info(f"Repository cloned successfully")
            
            # Clean up key file
            if deploy_key and os.path.exists(key_file):
                os.remove(key_file)
                
        except Exception as e:
            logger.error(f"Failed to clone repository: {str(e)}")
            raise
    
    def fetch(self, repo_path):
        """Fetch latest changes from remote"""
        try:
            repo = Repo(repo_path)
            origin = repo.remotes.origin
            origin.fetch()
            logger.info(f"Fetched latest changes for {repo_path}")
        except Exception as e:
            logger.error(f"Failed to fetch repository: {str(e)}")
            raise
    
    def checkout(self, repo_path, ref):
        """Checkout a specific commit/branch/tag"""
        try:
            repo = Repo(repo_path)
            repo.git.checkout(ref)
            logger.info(f"Checked out {ref} in {repo_path}")
        except Exception as e:
            logger.error(f"Failed to checkout {ref}: {str(e)}")
            raise
    
    def get_latest_commit(self, repo_path, branch='main'):
        """Get the latest commit SHA for a branch"""
        try:
            repo = Repo(repo_path)
            
            # Try to get remote branch
            try:
                remote_branch = repo.remotes.origin.refs[branch]
                return str(remote_branch.commit)
            except:
                # Fall back to local branch
                local_branch = repo.heads[branch]
                return str(local_branch.commit)
                
        except Exception as e:
            logger.error(f"Failed to get latest commit: {str(e)}")
            raise
    
    def get_commit_info(self, repo_path, commit_sha):
        """Get information about a specific commit"""
        try:
            repo = Repo(repo_path)
            commit = repo.commit(commit_sha)
            
            return {
                'sha': str(commit),
                'message': commit.message.strip(),
                'author': f"{commit.author.name} <{commit.author.email}>",
                'date': datetime.fromtimestamp(commit.committed_date),
                'short_sha': str(commit)[:8]
            }
        except Exception as e:
            logger.error(f"Failed to get commit info: {str(e)}")
            raise
    
    def get_current_branch(self, repo_path):
        """Get the current branch name"""
        try:
            repo = Repo(repo_path)
            return repo.active_branch.name
        except Exception as e:
            logger.error(f"Failed to get current branch: {str(e)}")
            raise
    
    def get_tags(self, repo_path):
        """Get all tags in the repository"""
        try:
            repo = Repo(repo_path)
            return [tag.name for tag in repo.tags]
        except Exception as e:
            logger.error(f"Failed to get tags: {str(e)}")
            raise
    
    def create_tag(self, repo_path, tag_name, message=None):
        """Create a new tag"""
        try:
            repo = Repo(repo_path)
            if message:
                repo.create_tag(tag_name, message=message)
            else:
                repo.create_tag(tag_name)
            logger.info(f"Created tag {tag_name} in {repo_path}")
        except Exception as e:
            logger.error(f"Failed to create tag: {str(e)}")
            raise