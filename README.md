# PyDeployer

A Django-based deployment orchestration system that replaces Docker containers with Python virtual environments, designed to run multiple Python applications on a single server efficiently.

## Features

- **Self-Managing**: PyDeployer can deploy and manage itself
- **Multi-Environment Support**: QA, Staging, and Production environments
- **Zero-Downtime Deployments**: Graceful service reloads with rollback capability
- **GitLab Integration**: Webhook support for automated deployments
- **REST API**: Full API for deployment automation
- **Django Admin**: Web interface for monitoring and management
- **Health Checks**: Automatic service health monitoring
- **Resource Management**: CPU and memory limits per service
- **Supervisor Integration**: Process management and auto-restart
- **Nginx Integration**: Automatic reverse proxy configuration

## Architecture

PyDeployer manages deployments by:
1. Creating isolated Python virtual environments for each project/environment
2. Using Supervisor to manage processes
3. Configuring Nginx as a reverse proxy
4. Tracking deployments in PostgreSQL
5. Providing REST API and Django Admin interfaces

## Installation

### Prerequisites

- Ubuntu/Debian server (16GB RAM, 4 CPUs recommended)
- Python 3.11+
- PostgreSQL 12+
- Redis
- Nginx
- Supervisor
- Git

### Initial Setup

1. **Install system dependencies:**
```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3-pip git nginx supervisor postgresql-client redis-server
```

2. **Create deployment user:**
```bash
sudo useradd -m -s /bin/bash deploy
sudo mkdir -p /opt/deployments/{apps,repos,nginx/sites,supervisor/conf.d}
sudo chown -R deploy:deploy /opt/deployments
```

3. **Setup PostgreSQL database:**
```sql
CREATE DATABASE pydeployer;
CREATE USER deployer WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE pydeployer TO deployer;
```

4. **Clone and setup PyDeployer:**
```bash
sudo su - deploy
cd /opt/deployments/apps
git clone https://gitlab.com/company/pydeployer.git pydeployer/releases/initial
cd pydeployer
python3.11 -m venv envs/prod
source envs/prod/bin/activate
pip install -r releases/initial/requirements.txt
```

5. **Configure environment:**
```bash
cd releases/initial
cp .env.example .env
# Edit .env with your configuration
nano .env
```

6. **Initialize database:**
```bash
export DATABASE_URL="postgresql://deployer:password@localhost/pydeployer"
cd src
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

7. **Register PyDeployer for self-management:**
```bash
python manage.py register_self
```

8. **Start PyDeployer:**
```bash
gunicorn --bind 127.0.0.1:8000 --workers=2 --threads=4 pydeployer.wsgi
```

## Usage

### CLI Commands

**Deploy a project:**
```bash
cd /opt/deployments/apps/pydeployer/releases/current/src
python manage.py deploy <project_name> --env=<environment>
python manage.py deploy uno-admin --env=prod
```

**Rollback deployment:**
```bash
cd /opt/deployments/apps/pydeployer/releases/current/src
python manage.py rollback <project_name> --env=<environment>
python manage.py rollback uno-admin --env=prod
```

**Register new project:**
```bash
cd /opt/deployments/apps/pydeployer/releases/current/src
python manage.py register_project <name> --repo=<git_url> --port-start=<port>
python manage.py register_project my-app --repo=git@gitlab.com:company/my-app.git --port-start=8100
```

### REST API

**Get authentication token:**
```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -d "username=admin&password=password"
```

**Deploy via API:**
```bash
curl -X POST http://localhost:8000/api/deploy/ \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "uno-admin",
    "environment": "prod",
    "commit_sha": "abc123"
  }'
```

**Check status:**
```bash
curl http://localhost:8000/api/status/ \
  -H "Authorization: Token <your-token>"
```

### Project Configuration

Each project needs deployment configuration files:

**deploy-prod.yaml:**
```yaml
name: my-app
environment: production
python_version: "3.11"
requirements: requirements.txt

services:
  - name: web
    type: django
    command: gunicorn --bind 127.0.0.1:${PORT} --workers=2 project.wsgi
    enabled: true
    health_check:
      endpoint: /health/
      interval: 30
    resources:
      max_memory: 2048
      max_cpu: 1.0
  
  - name: worker
    type: celery
    command: celery -A project worker --concurrency=2 -Q ${QUEUE_NAME}
    enabled: true

env_vars:
  DJANGO_SETTINGS_MODULE: project.settings_production
  DATABASE_URL: ${SECRET_DATABASE_URL}
  REDIS_URL: ${SECRET_REDIS_URL}

hooks:
  pre_deploy:
    - python manage.py migrate --noinput
    - python manage.py collectstatic --noinput
  post_deploy:
    - python manage.py check --deploy
```

### GitLab CI Integration

Add to your `.gitlab-ci.yml`:
```yaml
deploy:
  stage: deploy
  script:
    - |
      curl -X POST https://deploy.company.com/webhook/gitlab/ \
        -H "X-Gitlab-Token: $WEBHOOK_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$CI_WEBHOOK_PAYLOAD"
  only:
    - main
```

## Admin Interface

Access the Django admin at `http://localhost:8000/admin/` to:
- View and manage projects
- Monitor deployments
- Check service health
- View logs
- Manage environments and secrets

## Directory Structure

```
/opt/deployments/
├── apps/                    # Application deployments
│   ├── pydeployer/
│   │   ├── envs/           # Virtual environments
│   │   │   └── prod/
│   │   ├── releases/       # Versioned releases
│   │   │   ├── 20240102-1234/
│   │   │   └── current -> 20240102-1234/
│   │   └── logs/
│   └── my-app/
│       ├── envs/
│       ├── releases/
│       └── logs/
├── repos/                   # Git repository cache
├── nginx/
│   └── sites/              # Nginx configurations
└── supervisor/
    └── conf.d/             # Supervisor configurations
```

## Security

- All secrets are encrypted in the database
- Services run as non-privileged user
- Applications bind to localhost only
- Nginx handles SSL termination
- Webhook tokens for authentication
- Token-based API authentication

## Monitoring

PyDeployer provides:
- Health check endpoints for each service
- Deployment history and logs
- Service status monitoring
- Resource usage tracking
- Automatic restart on failure

## Troubleshooting

**Check service status:**
```bash
supervisorctl status
```

**View deployment logs:**
```bash
tail -f /opt/deployments/apps/<project>/logs/<environment>/*.log
```

**Manual rollback:**
```bash
cd /opt/deployments/apps/<project>/releases/<environment>
rm current
ln -s <previous-version> current
supervisorctl restart <project>-<environment>-*
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Your License]

## Support

For issues and questions, please contact the development team or create an issue in the repository.