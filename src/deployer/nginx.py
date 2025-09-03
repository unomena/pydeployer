import os
import subprocess
import logging
from django.conf import settings

logger = logging.getLogger('deployer')


class NginxManager:
    """Manage Nginx configurations"""
    
    def create_config(self, environment, web_services):
        """Create nginx configuration for an environment"""
        try:
            if not web_services:
                logger.info("No web services to configure for nginx")
                return
            
            # Prepare upstream servers
            upstreams = []
            for service in web_services:
                if service.port:
                    upstreams.append(f"    server 127.0.0.1:{service.port} max_fails=3 fail_timeout=30s;")
            
            if not upstreams:
                logger.warning("No services with ports configured")
                return
            
            # Generate configuration
            config_name = f"{environment.project.name}-{environment.name}"
            upstream_name = config_name.replace('-', '_')
            
            # Determine server name
            if environment.domain:
                server_name = environment.domain
            else:
                # Generate default domain
                server_name = "_"  # Accept any hostname
            
            config_content = self._generate_config(
                upstream_name=upstream_name,
                upstreams='\n'.join(upstreams),
                server_name=server_name,
                ssl_enabled=environment.ssl_enabled,
                environment=environment
            )
            
            # Write configuration file
            config_path = os.path.join(
                settings.NGINX_CONFIG_DIR,
                f"{config_name}.conf"
            )
            
            os.makedirs(settings.NGINX_CONFIG_DIR, exist_ok=True)
            
            with open(config_path, 'w') as f:
                f.write(config_content)
            
            logger.info(f"Created nginx config for {config_name}")
            
            # Test configuration
            self.test_config()
            
        except Exception as e:
            logger.error(f"Failed to create nginx config: {str(e)}")
            raise
    
    def _generate_config(self, upstream_name, upstreams, server_name, ssl_enabled, environment):
        """Generate nginx configuration content"""
        
        if ssl_enabled:
            # SSL configuration
            config = f"""upstream {upstream_name} {{
{upstreams}
    keepalive 32;
}}

server {{
    listen 80;
    server_name {server_name};
    return 301 https://$server_name$request_uri;
}}

server {{
    listen 443 ssl http2;
    server_name {server_name};
    
    ssl_certificate /etc/ssl/certs/{environment.project.name}-{environment.name}.crt;
    ssl_certificate_key /etc/ssl/private/{environment.project.name}-{environment.name}.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    client_max_body_size 100M;
    
    location / {{
        proxy_pass http://{upstream_name};
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}
    
    location /static/ {{
        alias /srv/deployments/apps/{environment.project.name}/releases/{environment.name}/current/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }}
    
    location /media/ {{
        alias /srv/deployments/apps/{environment.project.name}/media/;
        expires 7d;
    }}
    
    location /health/ {{
        proxy_pass http://{upstream_name}/health/;
        access_log off;
    }}
}}"""
        else:
            # Non-SSL configuration
            config = f"""upstream {upstream_name} {{
{upstreams}
    keepalive 32;
}}

server {{
    listen 80;
    server_name {server_name};
    
    client_max_body_size 100M;
    
    location / {{
        proxy_pass http://{upstream_name};
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}
    
    location /static/ {{
        alias /srv/deployments/apps/{environment.project.name}/releases/{environment.name}/current/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }}
    
    location /media/ {{
        alias /srv/deployments/apps/{environment.project.name}/media/;
        expires 7d;
    }}
    
    location /health/ {{
        proxy_pass http://{upstream_name}/health/;
        access_log off;
    }}
}}"""
        
        return config
    
    def test_config(self):
        """Test nginx configuration"""
        try:
            result = subprocess.run(
                ['sudo', 'nginx', '-t'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Nginx configuration test failed: {result.stderr}")
            
            logger.info("Nginx configuration test passed")
            
        except Exception as e:
            logger.error(f"Failed to test nginx config: {str(e)}")
            raise
    
    def reload(self):
        """Reload nginx configuration"""
        try:
            # Test configuration first
            self.test_config()
            
            # Reload nginx
            subprocess.run(['sudo', 'nginx', '-s', 'reload'], check=True, capture_output=True)
            logger.info("Nginx reloaded successfully")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reload nginx: {e.stderr}")
            raise
    
    def remove_config(self, environment):
        """Remove nginx configuration for an environment"""
        try:
            config_name = f"{environment.project.name}-{environment.name}"
            config_path = os.path.join(
                settings.NGINX_CONFIG_DIR,
                f"{config_name}.conf"
            )
            
            if os.path.exists(config_path):
                os.remove(config_path)
                logger.info(f"Removed nginx config for {config_name}")
                
                # Reload nginx
                self.reload()
                
        except Exception as e:
            logger.error(f"Failed to remove nginx config: {str(e)}")
            raise
    
    def get_status(self):
        """Get nginx status"""
        try:
            result = subprocess.run(
                ['systemctl', 'status', 'nginx'],
                capture_output=True,
                text=True
            )
            
            if 'active (running)' in result.stdout:
                return 'running'
            elif 'inactive' in result.stdout:
                return 'stopped'
            elif 'failed' in result.stdout:
                return 'failed'
            else:
                return 'unknown'
                
        except Exception as e:
            logger.error(f"Failed to get nginx status: {str(e)}")
            return 'unknown'