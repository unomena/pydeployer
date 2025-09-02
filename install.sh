#!/bin/bash
set -e

# PyDeployer Installation Script
# This script installs PyDeployer on a fresh Ubuntu LTS server
# Run as: curl -fsSL https://raw.githubusercontent.com/yourusername/pydeployer/main/install.sh | sudo bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DEPLOYMENT_ROOT="/srv/deployments"
DEPLOYMENT_USER="deploy"
DB_NAME="pydeployer"
DB_USER="deployer"
DB_PASSWORD="deployer_pass_2024"
REPO_URL="${REPO_URL:-https://github.com/unomena/pydeployer.git}"
GITLAB_TOKEN="${GITLAB_TOKEN:-}"
SERVER_IP=$(hostname -I | awk '{print $1}')

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run as root or with sudo"
fi

print_status "Starting PyDeployer installation..."

# Update system
print_status "Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

# Install system dependencies
print_status "Installing system dependencies..."
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    build-essential \
    postgresql \
    postgresql-contrib \
    nginx \
    supervisor \
    redis-server \
    curl \
    wget \
    sudo \
    libpq-dev

# Create deployment user
print_status "Creating deployment user..."
if ! id -u $DEPLOYMENT_USER > /dev/null 2>&1; then
    useradd -m -s /bin/bash $DEPLOYMENT_USER
    usermod -aG sudo $DEPLOYMENT_USER
    echo "$DEPLOYMENT_USER ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/$DEPLOYMENT_USER
fi

# Create directory structure
print_status "Creating directory structure..."
mkdir -p $DEPLOYMENT_ROOT/{apps,repos,nginx/sites,supervisor/conf.d,backups}
mkdir -p $DEPLOYMENT_ROOT/apps/pydeployer/{releases,envs,logs,media}
mkdir -p $DEPLOYMENT_ROOT/apps/pydeployer/logs/{prod,qa,stage}
chown -R $DEPLOYMENT_USER:$DEPLOYMENT_USER $DEPLOYMENT_ROOT

# Configure PostgreSQL
print_status "Configuring PostgreSQL..."
sudo -u postgres psql <<EOF
-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;

-- Create database if not exists
SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF

# Configure Redis
print_status "Configuring Redis..."
systemctl enable redis-server
systemctl start redis-server

# Clone PyDeployer repository
print_status "Cloning PyDeployer repository..."
if [ -d "$DEPLOYMENT_ROOT/repos/pydeployer" ]; then
    print_warning "Repository already exists, pulling latest changes..."
    sudo -u $DEPLOYMENT_USER git -C $DEPLOYMENT_ROOT/repos/pydeployer pull
else
    # Check for local directory first
    if [ -d "/tmp/pydeployer" ]; then
        # Use local directory if available
        print_status "Using local PyDeployer directory..."
        sudo -u $DEPLOYMENT_USER cp -r /tmp/pydeployer $DEPLOYMENT_ROOT/repos/
    elif [ -d "/tmp/py-deployer" ]; then
        # Also check for py-deployer name
        print_status "Using local py-deployer directory..."
        sudo -u $DEPLOYMENT_USER cp -r /tmp/py-deployer $DEPLOYMENT_ROOT/repos/pydeployer
    elif [ -f "/tmp/pydeployer.tar.gz" ]; then
        # Use local archive if available
        print_status "Using local PyDeployer archive..."
        sudo -u $DEPLOYMENT_USER tar -xzf /tmp/pydeployer.tar.gz -C $DEPLOYMENT_ROOT/repos/
        sudo -u $DEPLOYMENT_USER mv $DEPLOYMENT_ROOT/repos/pydeployer-* $DEPLOYMENT_ROOT/repos/pydeployer 2>/dev/null || true
    elif [[ $REPO_URL == *"gitlab.com"* ]] && [ -n "$GITLAB_TOKEN" ]; then
        # Use token for authentication
        AUTH_URL=$(echo $REPO_URL | sed "s|https://|https://oauth2:${GITLAB_TOKEN}@|")
        sudo -u $DEPLOYMENT_USER git clone $AUTH_URL $DEPLOYMENT_ROOT/repos/pydeployer
    else
        # Try SSH URL as fallback
        SSH_URL=$(echo $REPO_URL | sed 's|https://gitlab.com/|git@gitlab.com:|')
        print_status "Trying SSH clone..."
        if sudo -u $DEPLOYMENT_USER git clone $SSH_URL $DEPLOYMENT_ROOT/repos/pydeployer 2>/dev/null; then
            print_status "Successfully cloned via SSH"
        else
            print_error "Cannot access repository. Please provide one of:
            - SSH access to GitLab
            - GITLAB_TOKEN environment variable for private repo
            - /tmp/pydeployer or /tmp/py-deployer directory
            - /tmp/pydeployer.tar.gz archive file"
        fi
    fi
fi

# Create initial release
print_status "Creating initial release..."
RELEASE_DIR="$DEPLOYMENT_ROOT/apps/pydeployer/releases/initial"
if [ ! -d "$RELEASE_DIR" ]; then
    sudo -u $DEPLOYMENT_USER mkdir -p $RELEASE_DIR
    sudo -u $DEPLOYMENT_USER cp -r $DEPLOYMENT_ROOT/repos/pydeployer/* $RELEASE_DIR/
fi

# Create Python virtual environment
print_status "Creating Python virtual environment..."
VENV_PATH="$DEPLOYMENT_ROOT/apps/pydeployer/envs/prod"
if [ ! -d "$VENV_PATH" ]; then
    sudo -u $DEPLOYMENT_USER python3 -m venv $VENV_PATH
fi

# Install Python dependencies
print_status "Installing Python dependencies..."
sudo -u $DEPLOYMENT_USER $VENV_PATH/bin/pip install --upgrade pip setuptools wheel
sudo -u $DEPLOYMENT_USER $VENV_PATH/bin/pip install -r $RELEASE_DIR/requirements.txt

# Create environment file
print_status "Creating environment configuration..."
cat > $RELEASE_DIR/.env <<EOF
# PyDeployer Environment Variables
SECRET_KEY=django-insecure-$(openssl rand -hex 32)
DEBUG=0
ALLOWED_HOSTS=*

# Database Configuration
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Deployment Settings
DEPLOYMENT_ROOT=$DEPLOYMENT_ROOT
DEPLOYMENT_USER=$DEPLOYMENT_USER

# CORS Settings
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# Encryption Key for Secrets
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# PyDeployer Self-Management
PYDEPLOYER_REPO=https://github.com/unomena/pydeployer.git
EOF

chown $DEPLOYMENT_USER:$DEPLOYMENT_USER $RELEASE_DIR/.env

# Set up symlink
print_status "Creating symlink to current release..."
sudo -u $DEPLOYMENT_USER ln -sfn $RELEASE_DIR $DEPLOYMENT_ROOT/apps/pydeployer/releases/current

# Run database migrations
print_status "Running database migrations..."
cd $RELEASE_DIR/src
sudo -u $DEPLOYMENT_USER bash -c "source ../.env && DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME $VENV_PATH/bin/python manage.py makemigrations core api deployer webhooks --noinput"
sudo -u $DEPLOYMENT_USER bash -c "source ../.env && DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME $VENV_PATH/bin/python manage.py migrate --noinput"

# Collect static files
print_status "Collecting static files..."
# Create a temporary writable log file
touch /tmp/deployer.log
chmod 666 /tmp/deployer.log
sudo -u $DEPLOYMENT_USER bash -c "source ../.env && DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME $VENV_PATH/bin/python manage.py collectstatic --noinput"

# Create superuser
print_status "Creating superuser..."
sudo -u $DEPLOYMENT_USER bash -c "source ../.env && DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME $VENV_PATH/bin/python manage.py shell" <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@pydeployer.local', 'admin123')
    print("Superuser created: admin / admin123")
else:
    print("Superuser already exists")
EOF

# Configure Supervisor
print_status "Configuring Supervisor..."
# Get the encryption key from .env file
ENCRYPTION_KEY=$(grep ENCRYPTION_KEY $RELEASE_DIR/.env | cut -d= -f2)
cat > /etc/supervisor/conf.d/pydeployer.conf <<EOF
[program:pydeployer-web]
command=$VENV_PATH/bin/gunicorn --bind 0.0.0.0:8000 --workers=2 --threads=4 --worker-class=gthread pydeployer.wsgi
directory=$RELEASE_DIR/src
user=$DEPLOYMENT_USER
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=30
killasgroup=true
stopasgroup=true
stdout_logfile=$DEPLOYMENT_ROOT/apps/pydeployer/logs/prod/web_stdout.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
stderr_logfile=$DEPLOYMENT_ROOT/apps/pydeployer/logs/prod/web_stderr.log
stderr_logfile_maxbytes=10MB
stderr_logfile_backups=5
environment=DJANGO_SETTINGS_MODULE="pydeployer.settings",PYTHONUNBUFFERED="1",DEBUG="0",ALLOWED_HOSTS="*",DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME",DEPLOYMENT_ROOT="$DEPLOYMENT_ROOT",ENCRYPTION_KEY="$ENCRYPTION_KEY"
EOF

# Configure Nginx
print_status "Configuring Nginx..."
cat > /etc/nginx/sites-available/pydeployer <<EOF
upstream pydeployer_backend {
    server 127.0.0.1:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

server {
    listen 80;
    server_name _;
    
    client_max_body_size 100M;
    
    location / {
        proxy_pass http://pydeployer_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host localhost;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    location /static/ {
        alias $RELEASE_DIR/src/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias $DEPLOYMENT_ROOT/apps/pydeployer/media/;
        expires 7d;
    }
    
    location /health/ {
        proxy_set_header Host localhost;
        proxy_pass http://pydeployer_backend/health/;
        access_log off;
    }
}
EOF

# Enable nginx site
ln -sf /etc/nginx/sites-available/pydeployer /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Create sudoers entries for deployment user
print_status "Configuring sudo permissions..."
cat > /etc/sudoers.d/pydeployer <<EOF
# PyDeployer deployment user permissions
$DEPLOYMENT_USER ALL=(ALL) NOPASSWD: /usr/bin/supervisorctl *
$DEPLOYMENT_USER ALL=(ALL) NOPASSWD: /usr/sbin/nginx *
$DEPLOYMENT_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart supervisor
$DEPLOYMENT_USER ALL=(ALL) NOPASSWD: /bin/systemctl reload nginx
$DEPLOYMENT_USER ALL=(postgres) NOPASSWD: /usr/bin/psql
EOF

# Start services
print_status "Starting services..."
systemctl restart supervisor
sleep 2  # Wait for supervisor to fully start
supervisorctl reread || true
supervisorctl update || true
supervisorctl start pydeployer-web || supervisorctl restart pydeployer-web || true
nginx -t && systemctl restart nginx

# Register PyDeployer with itself
print_status "Registering PyDeployer with itself..."
sleep 5  # Wait for services to start

# Create deploy configuration
cat > $DEPLOYMENT_ROOT/repos/pydeployer/deploy-prod.yaml <<EOF
name: pydeployer
environment: production
python_version: "3.11"
requirements: requirements.txt

services:
  - name: web
    type: django
    command: gunicorn --bind 0.0.0.0:\${PORT} --workers=2 --threads=4 --worker-class=gthread pydeployer.wsgi
    enabled: true
    health_check:
      endpoint: /api/status/
      interval: 60
    resources:
      max_memory: 1024
      max_cpu: 0.5

env_vars:
  DJANGO_SETTINGS_MODULE: pydeployer.settings
  PYTHONUNBUFFERED: "1"
  DEBUG: "0"
  ALLOWED_HOSTS: "*"
  DATABASE_URL: "postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME"
  REDIS_URL: "redis://localhost:6379/0"
  SECRET_KEY: "django-insecure-prod-key-please-change-in-production"
  DEPLOYMENT_ROOT: "$DEPLOYMENT_ROOT"
  DEPLOYMENT_USER: "$DEPLOYMENT_USER"
  ENCRYPTION_KEY: "will-be-loaded-from-env-file"

hooks:
  pre_deploy:
    - cd src && python manage.py migrate --noinput
    - cd src && python manage.py collectstatic --noinput
    - cd src && python manage.py check --deploy
  post_deploy:
    - cd src && python manage.py check
EOF

chown $DEPLOYMENT_USER:$DEPLOYMENT_USER $DEPLOYMENT_ROOT/repos/pydeployer/deploy-prod.yaml

# Register and deploy PyDeployer
cd $DEPLOYMENT_ROOT/repos/pydeployer
sudo -u $DEPLOYMENT_USER $VENV_PATH/bin/python $RELEASE_DIR/src/manage.py shell <<EOF
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'pydeployer.settings'
from core.models import Project, Environment
from deployer.executor import DeploymentExecutor

# Register project if not exists
if not Project.objects.filter(name='pydeployer').exists():
    project = Project.objects.create(
        name='pydeployer',
        repository_url='https://github.com/unomena/pydeployer.git',
        description='PyDeployer - Python Deployment Orchestration System',
        port_start=8000
    )
    
    # Create production environment
    Environment.objects.create(
        project=project,
        name='prod',
        active=True
    )
    
    print("PyDeployer project registered successfully")
    
    # Trigger initial deployment (optional, may fail if repo not accessible)
    try:
        executor = DeploymentExecutor()
        deployment = executor.deploy(
            project_name='pydeployer',
            environment_name='prod',
            deployed_by='installer'
        )
        print(f"Initial deployment triggered: {deployment.id}")
    except Exception as e:
        print(f"Could not trigger deployment (this is normal for initial setup): {e}")
else:
    print("PyDeployer already registered")
EOF

# Final status check
print_status "Checking deployment status..."
sleep 10  # Wait for services to fully start

# Check health endpoint
if curl -s http://localhost/health/ | python3 -m json.tool 2>/dev/null; then
    print_status "Health check passed!"
else
    print_warning "Health check endpoint not ready yet. This is normal - services may take a moment to start."
    print_warning "You can check status later with: curl http://$SERVER_IP/health/"
fi

# Print completion message
echo ""
echo "========================================"
echo -e "${GREEN}PyDeployer installation completed!${NC}"
echo "========================================"
echo ""
echo "Access PyDeployer at: http://$SERVER_IP/"
echo "Admin interface: http://$SERVER_IP/admin/"
echo "Username: admin"
echo "Password: admin123"
echo ""
echo "API Health Check: http://$SERVER_IP/health/"
echo ""
echo -e "${YELLOW}IMPORTANT: Please change the admin password after first login!${NC}"
echo ""