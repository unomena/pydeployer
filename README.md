# PyDeployer

A Django-based deployment orchestration system that replaces Docker containers with Python virtual environments, designed to run multiple Python applications on a single server efficiently.

## 🚀 Quick Installation (One Command)

Install PyDeployer on a fresh Ubuntu LTS server with a single command:

```bash
curl -fsSL https://gitlab.com/company/pydeployer/-/raw/main/install.sh | sudo bash
```

This will:
- Install all system dependencies (PostgreSQL, Nginx, Supervisor, Redis)
- Create deployment user and directory structure
- Configure database and services
- Deploy PyDeployer itself
- Create admin user (admin/admin123)
- Start all services

After installation, access PyDeployer at: `http://YOUR_SERVER_IP/`

## 🚀 Alternative: Manual Setup with Makefile

If you prefer to clone and install manually:

```bash
# Clone the repository
git clone https://gitlab.com/company/pydeployer.git
cd pydeployer

# One command to rule them all
make quickstart

# Create your admin user
make create-superuser

# Start PyDeployer
make start

# Register your first project
make register-project NAME=my-app REPO=git@gitlab.com:my-org/my-app.git PORT=8100

# Deploy it!
make deploy PROJECT=my-app ENV=prod

# Access admin at http://localhost:8000/admin
```

That's it! You're deployed! 🎉

---

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

The Makefile provides automated installation commands that handle all setup steps. You can use `make quickstart` for a complete automated setup, or follow the manual steps below.

### Prerequisites

- Ubuntu LTS (20.04 or 22.04 recommended)
- sudo access
- Git
- 16GB RAM, 4 CPUs (recommended for production)

### Automated Setup with Makefile

The easiest way to install PyDeployer is using the included Makefile:

```bash
# Complete automated setup
make quickstart

# This will:
# 1. Install all system dependencies (Python 3.11, Nginx, Supervisor, Redis)
# 2. Install and configure PostgreSQL
# 3. Create deployment user and directory structure in /srv/deployments
# 4. Install PyDeployer
# 5. Initialize the database
# 6. Register PyDeployer for self-management
```

### Manual Setup

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

## Makefile Commands

The Makefile provides convenient commands for all PyDeployer operations. All commands can be viewed with `make help`.

### 📦 Installation & Setup

| Command | Description |
|---------|-------------|
| `make quickstart` | Complete automated setup from scratch |
| `make install-postgres` | Install PostgreSQL (latest stable) |
| `make setup-database` | Create PyDeployer database and user |
| `make install-system-deps` | Install all system dependencies |
| `make create-deployment-user` | Create deploy user and `/srv/deployments` structure |
| `make install-pydeployer` | Install PyDeployer to `/srv/deployments` |
| `make configure-pydeployer` | Configure environment variables |
| `make init-database` | Initialize database with migrations |
| `make create-superuser` | Create Django admin user |
| `make register-self` | Register PyDeployer to manage itself |

### 🚀 Deployment Operations

| Command | Description | Example |
|---------|-------------|---------|
| `make deploy` | Deploy a project | `make deploy PROJECT=my-app ENV=prod` |
| `make rollback` | Rollback deployment | `make rollback PROJECT=my-app ENV=prod` |
| `make register-project` | Register new project | `make register-project NAME=my-app REPO=git@... PORT=8100` |
| `make list-projects` | List all registered projects | `make list-projects` |
| `make list-deployments` | Show recent deployments | `make list-deployments` |

### 🔧 Service Management

| Command | Description |
|---------|-------------|
| `make start` | Start PyDeployer service |
| `make stop` | Stop PyDeployer service |
| `make restart` | Restart PyDeployer service |
| `make status` | Check all services status |
| `make logs` | View PyDeployer logs (tail -f) |

### 🛠️ Development Tools

| Command | Description |
|---------|-------------|
| `make shell` | Open Django shell |
| `make dbshell` | Open PostgreSQL shell |
| `make migrate` | Apply database migrations |
| `make makemigrations` | Create new migrations |
| `make test` | Run test suite |
| `make collectstatic` | Collect static files |
| `make clean` | Clean temporary files |

### 💡 Common Workflows

**First Time Setup:**
```bash
make quickstart
make create-superuser
make start
```

**Register and Deploy a Project:**
```bash
# Register the project
make register-project NAME=uno-admin REPO=git@gitlab.com:unomena/uno-admin.git PORT=8100

# Deploy to QA
make deploy PROJECT=uno-admin ENV=qa

# Deploy to Production
make deploy PROJECT=uno-admin ENV=prod

# If something goes wrong, rollback
make rollback PROJECT=uno-admin ENV=prod
```

**Daily Operations:**
```bash
# Check status
make status

# View recent deployments
make list-deployments

# Watch logs
make logs

# Restart if needed
make restart
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

The Makefile sets up the following directory structure in `/srv/deployments` (note: changed from `/opt/deployments` for better compliance with Linux FHS):

```
/srv/deployments/
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

### Using Makefile Commands

**Check all services:**
```bash
make status
```

**View logs:**
```bash
make logs
```

**If PostgreSQL installation fails:**
```bash
# Check Ubuntu version
lsb_release -a

# Manually run the install script
bash scripts/install_postgres.sh

# Or install PostgreSQL manually
sudo apt-get install postgresql postgresql-contrib
```

**If deployment fails:**
```bash
# Check project registration
make list-projects

# Check recent deployments
make list-deployments

# View detailed logs
make logs

# Try manual deployment
make shell
# Then in shell:
from deployer.executor import DeploymentExecutor
executor = DeploymentExecutor()
executor.deploy('project-name', 'qa')
```

**Permission issues:**
```bash
# Ensure deploy user owns directories
sudo chown -R deploy:deploy /srv/deployments

# Check deploy user exists
id deploy
```

### Manual Operations

**Check service status:**
```bash
supervisorctl status
```

**View deployment logs:**
```bash
tail -f /srv/deployments/apps/<project>/logs/<environment>/*.log
```

**Manual rollback:**
```bash
cd /srv/deployments/apps/<project>/releases/<environment>
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