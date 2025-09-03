"""
Show the deploy user's SSH public key
"""
import os
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Display the deploy user SSH public key'

    def handle(self, *args, **options):
        deploy_user = getattr(settings, 'DEPLOYMENT_USER', 'deploy')
        key_paths = [
            f'/home/{deploy_user}/.ssh/id_ed25519.pub',
            f'/home/{deploy_user}/.ssh/id_rsa.pub',
        ]
        
        key_found = False
        for key_path in key_paths:
            if os.path.exists(key_path):
                with open(key_path, 'r') as f:
                    public_key = f.read().strip()
                
                self.stdout.write("=" * 60)
                self.stdout.write(self.style.SUCCESS("PyDeployer SSH Deploy Key"))
                self.stdout.write("=" * 60)
                self.stdout.write(public_key)
                self.stdout.write("")
                self.stdout.write("=" * 60)
                self.stdout.write("Add this key to your Git repository:")
                self.stdout.write("- GitLab: Settings -> Repository -> Deploy Keys")
                self.stdout.write("- GitHub: Settings -> Deploy keys")
                self.stdout.write("=" * 60)
                key_found = True
                break
        
        if not key_found:
            self.stdout.write(self.style.ERROR("No SSH key found for deploy user!"))
            self.stdout.write("Generate one by running:")
            self.stdout.write("  make setup-deploy-key")
            self.stdout.write("Or if using the installation script, the key is generated automatically.")