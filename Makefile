# PyDeployer Makefile
# Deployment orchestration system management

# Variables
PYTHON := python3
PIP := pip3
DEPLOYMENT_ROOT := /srv/deployments
DEPLOYMENT_USER := deploy
DB_NAME := pydeployer
DB_USER := deployer
DB_PASS := deployer_pass_2024
VENV_PATH := $(DEPLOYMENT_ROOT)/apps/pydeployer/envs/prod
MANAGE_PY := cd $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/src && $(VENV_PATH)/bin/python manage.py
CURRENT_DIR := $(shell pwd)

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

.PHONY: help
help: ## Show this help message
	@echo "PyDeployer Management Commands"
	@echo "=============================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "Usage: make [target]"

# ==================== Installation Targets ====================

.PHONY: install-postgres
install-postgres: ## Install PostgreSQL on Ubuntu
	@echo "$(YELLOW)Installing PostgreSQL...$(NC)"
	@bash $(CURRENT_DIR)/scripts/install_postgres.sh

.PHONY: setup-database
setup-database: ## Create PyDeployer database and user
	@echo "$(YELLOW)Setting up PostgreSQL database...$(NC)"
	@sudo -u postgres psql -c "CREATE USER $(DB_USER) WITH PASSWORD '$(DB_PASS)';" || true
	@sudo -u postgres psql -c "CREATE DATABASE $(DB_NAME) OWNER $(DB_USER);" || true
	@sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $(DB_NAME) TO $(DB_USER);"
	@echo "$(GREEN)Database setup complete!$(NC)"
	@echo "Database: $(DB_NAME)"
	@echo "User: $(DB_USER)"
	@echo "Connection string: postgresql://$(DB_USER):$(DB_PASS)@localhost/$(DB_NAME)"

.PHONY: install-system-deps
install-system-deps: ## Install system dependencies
	@echo "$(YELLOW)Installing system dependencies...$(NC)"
	@sudo apt-get update
	@sudo apt-get install -y \
		python3.11 python3.11-venv python3-pip \
		git nginx supervisor redis-server \
		build-essential libpq-dev python3-dev \
		curl wget vim htop
	@echo "$(GREEN)System dependencies installed!$(NC)"

.PHONY: create-deployment-user
create-deployment-user: ## Create deployment user and directories
	@echo "$(YELLOW)Creating deployment user and directory structure...$(NC)"
	@sudo useradd -m -s /bin/bash $(DEPLOYMENT_USER) || true
	@sudo mkdir -p $(DEPLOYMENT_ROOT)/{apps,repos,nginx/sites,supervisor/conf.d,logs}
	@sudo chown -R $(DEPLOYMENT_USER):$(DEPLOYMENT_USER) $(DEPLOYMENT_ROOT)
	@sudo usermod -aG sudo $(DEPLOYMENT_USER) || true
	@echo "$(GREEN)Deployment user and directories created!$(NC)"

.PHONY: setup-environment
setup-environment: ## Complete environment setup
	@make install-system-deps
	@make install-postgres
	@make setup-database
	@make create-deployment-user
	@echo "$(GREEN)Environment setup complete!$(NC)"

# ==================== PyDeployer Setup ====================

.PHONY: install-pydeployer
install-pydeployer: ## Install PyDeployer for the first time
	@echo "$(YELLOW)Installing PyDeployer...$(NC)"
	@sudo mkdir -p $(DEPLOYMENT_ROOT)/apps/pydeployer/releases
	@sudo cp -r $(CURRENT_DIR) $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/initial
	@sudo chown -R $(DEPLOYMENT_USER):$(DEPLOYMENT_USER) $(DEPLOYMENT_ROOT)/apps/pydeployer
	@cd $(DEPLOYMENT_ROOT)/apps/pydeployer && sudo -u $(DEPLOYMENT_USER) python3.11 -m venv envs/prod
	@cd $(DEPLOYMENT_ROOT)/apps/pydeployer && sudo -u $(DEPLOYMENT_USER) envs/prod/bin/pip install --upgrade pip
	@cd $(DEPLOYMENT_ROOT)/apps/pydeployer && sudo -u $(DEPLOYMENT_USER) envs/prod/bin/pip install -r releases/initial/requirements.txt
	@sudo ln -sfn $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/initial $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current
	@echo "$(GREEN)PyDeployer installed!$(NC)"

.PHONY: configure-pydeployer
configure-pydeployer: ## Configure PyDeployer environment
	@echo "$(YELLOW)Configuring PyDeployer...$(NC)"
	@sudo cp $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env.example $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env
	@sudo sed -i 's|DATABASE_URL=.*|DATABASE_URL=postgresql://$(DB_USER):$(DB_PASS)@localhost/$(DB_NAME)|' $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env
	@sudo sed -i 's|DEPLOYMENT_ROOT=.*|DEPLOYMENT_ROOT=$(DEPLOYMENT_ROOT)|' $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env
	@sudo sed -i 's|DEPLOYMENT_USER=.*|DEPLOYMENT_USER=$(DEPLOYMENT_USER)|' $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env
	@sudo chown $(DEPLOYMENT_USER):$(DEPLOYMENT_USER) $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env
	@echo "$(GREEN)Configuration complete!$(NC)"

.PHONY: init-database
init-database: ## Initialize PyDeployer database
	@echo "$(YELLOW)Initializing database...$(NC)"
	@sudo -u $(DEPLOYMENT_USER) bash -c 'cd $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current && source ../.env && $(VENV_PATH)/bin/python src/manage.py migrate'
	@echo "$(GREEN)Database initialized!$(NC)"

.PHONY: create-superuser
create-superuser: ## Create Django superuser
	@echo "$(YELLOW)Creating superuser...$(NC)"
	@sudo -u $(DEPLOYMENT_USER) bash -c 'cd $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current && source ../.env && $(VENV_PATH)/bin/python src/manage.py createsuperuser'

.PHONY: collectstatic
collectstatic: ## Collect static files
	@echo "$(YELLOW)Collecting static files...$(NC)"
	@sudo -u $(DEPLOYMENT_USER) bash -c 'cd $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current && source ../.env && $(VENV_PATH)/bin/python src/manage.py collectstatic --noinput'
	@echo "$(GREEN)Static files collected!$(NC)"

.PHONY: register-self
register-self: ## Register PyDeployer to manage itself
	@echo "$(YELLOW)Registering PyDeployer for self-management...$(NC)"
	@sudo -u $(DEPLOYMENT_USER) bash -c 'cd $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current && source ../.env && $(VENV_PATH)/bin/python src/manage.py register_self'
	@echo "$(GREEN)PyDeployer registered!$(NC)"

# ==================== Service Management ====================

.PHONY: start
start: ## Start PyDeployer service
	@echo "$(YELLOW)Starting PyDeployer...$(NC)"
	@sudo -u $(DEPLOYMENT_USER) bash -c 'cd $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/src && \
		source ../../.env && \
		$(VENV_PATH)/bin/gunicorn --bind 127.0.0.1:8000 --workers 2 --threads 4 \
		--pid /tmp/pydeployer.pid --daemon pydeployer.wsgi'
	@echo "$(GREEN)PyDeployer started on port 8000!$(NC)"

.PHONY: stop
stop: ## Stop PyDeployer service
	@echo "$(YELLOW)Stopping PyDeployer...$(NC)"
	@if [ -f /tmp/pydeployer.pid ]; then \
		sudo kill $$(cat /tmp/pydeployer.pid) && rm /tmp/pydeployer.pid; \
		echo "$(GREEN)PyDeployer stopped!$(NC)"; \
	else \
		echo "$(YELLOW)PyDeployer is not running$(NC)"; \
	fi

.PHONY: restart
restart: ## Restart PyDeployer service
	@make stop
	@sleep 2
	@make start

.PHONY: status
status: ## Check PyDeployer status
	@echo "$(YELLOW)PyDeployer Status:$(NC)"
	@if [ -f /tmp/pydeployer.pid ] && kill -0 $$(cat /tmp/pydeployer.pid) 2>/dev/null; then \
		echo "$(GREEN)✓ PyDeployer is running (PID: $$(cat /tmp/pydeployer.pid))$(NC)"; \
	else \
		echo "$(RED)✗ PyDeployer is not running$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)PostgreSQL Status:$(NC)"
	@sudo systemctl is-active postgresql >/dev/null && echo "$(GREEN)✓ PostgreSQL is running$(NC)" || echo "$(RED)✗ PostgreSQL is not running$(NC)"
	@echo ""
	@echo "$(YELLOW)Nginx Status:$(NC)"
	@sudo systemctl is-active nginx >/dev/null && echo "$(GREEN)✓ Nginx is running$(NC)" || echo "$(RED)✗ Nginx is not running$(NC)"
	@echo ""
	@echo "$(YELLOW)Supervisor Status:$(NC)"
	@sudo systemctl is-active supervisor >/dev/null && echo "$(GREEN)✓ Supervisor is running$(NC)" || echo "$(RED)✗ Supervisor is not running$(NC)"

.PHONY: logs
logs: ## View PyDeployer logs
	@tail -f $(DEPLOYMENT_ROOT)/apps/pydeployer/logs/*.log 2>/dev/null || echo "No logs available yet"

# ==================== Deployment Commands ====================

.PHONY: deploy
deploy: ## Deploy a project (usage: make deploy PROJECT=myapp ENV=prod)
	@if [ -z "$(PROJECT)" ]; then \
		echo "$(RED)Error: PROJECT is required$(NC)"; \
		echo "Usage: make deploy PROJECT=myapp ENV=prod"; \
		exit 1; \
	fi
	@if [ -z "$(ENV)" ]; then \
		echo "$(RED)Error: ENV is required$(NC)"; \
		echo "Usage: make deploy PROJECT=myapp ENV=prod"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Deploying $(PROJECT) to $(ENV)...$(NC)"
	@sudo -u $(DEPLOYMENT_USER) bash -c 'source $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env && \
		$(MANAGE_PY) deploy $(PROJECT) --env=$(ENV)'

.PHONY: rollback
rollback: ## Rollback a deployment (usage: make rollback PROJECT=myapp ENV=prod)
	@if [ -z "$(PROJECT)" ]; then \
		echo "$(RED)Error: PROJECT is required$(NC)"; \
		echo "Usage: make rollback PROJECT=myapp ENV=prod"; \
		exit 1; \
	fi
	@if [ -z "$(ENV)" ]; then \
		echo "$(RED)Error: ENV is required$(NC)"; \
		echo "Usage: make rollback PROJECT=myapp ENV=prod"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Rolling back $(PROJECT) in $(ENV)...$(NC)"
	@sudo -u $(DEPLOYMENT_USER) bash -c 'source $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env && \
		$(MANAGE_PY) rollback $(PROJECT) --env=$(ENV)'

.PHONY: register-project
register-project: ## Register a new project (usage: make register-project NAME=myapp REPO=git@... PORT=8100)
	@if [ -z "$(NAME)" ]; then \
		echo "$(RED)Error: NAME is required$(NC)"; \
		echo "Usage: make register-project NAME=myapp REPO=git@gitlab.com:org/repo.git PORT=8100"; \
		exit 1; \
	fi
	@if [ -z "$(REPO)" ]; then \
		echo "$(RED)Error: REPO is required$(NC)"; \
		echo "Usage: make register-project NAME=myapp REPO=git@gitlab.com:org/repo.git PORT=8100"; \
		exit 1; \
	fi
	@if [ -z "$(PORT)" ]; then \
		echo "$(RED)Error: PORT is required$(NC)"; \
		echo "Usage: make register-project NAME=myapp REPO=git@gitlab.com:org/repo.git PORT=8100"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Registering project $(NAME)...$(NC)"
	@sudo -u $(DEPLOYMENT_USER) bash -c 'source $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env && \
		$(MANAGE_PY) register_project $(NAME) --repo=$(REPO) --port-start=$(PORT)'

.PHONY: list-projects
list-projects: ## List all registered projects
	@echo "$(YELLOW)Registered Projects:$(NC)"
	@sudo -u $(DEPLOYMENT_USER) bash -c 'source $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env && \
		echo "from core.models import Project; [print(f\"- {p.name}: {p.repository_url} (port: {p.port_start})\") for p in Project.objects.all()]" | \
		$(VENV_PATH)/bin/python $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/src/manage.py shell' 2>/dev/null

.PHONY: list-deployments
list-deployments: ## List recent deployments
	@echo "$(YELLOW)Recent Deployments:$(NC)"
	@sudo -u $(DEPLOYMENT_USER) bash -c 'source $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env && \
		echo "from core.models import Deployment; [print(f\"{d.deployed_at.strftime(\"%Y-%m-%d %H:%M\")}: {d.environment.project.name}-{d.environment.name} v{d.version} ({d.status})\") for d in Deployment.objects.all().order_by(\"-deployed_at\")[:10]]" | \
		$(VENV_PATH)/bin/python $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/src/manage.py shell' 2>/dev/null

# ==================== Development Commands ====================

.PHONY: shell
shell: ## Open Django shell
	@sudo -u $(DEPLOYMENT_USER) bash -c 'source $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env && \
		$(MANAGE_PY) shell'

.PHONY: dbshell
dbshell: ## Open database shell
	@sudo -u postgres psql -d $(DB_NAME)

.PHONY: test
test: ## Run tests
	@echo "$(YELLOW)Running tests...$(NC)"
	@sudo -u $(DEPLOYMENT_USER) bash -c 'source $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env && \
		$(MANAGE_PY) test'

.PHONY: makemigrations
makemigrations: ## Create new migrations
	@sudo -u $(DEPLOYMENT_USER) bash -c 'source $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env && \
		$(MANAGE_PY) makemigrations'

.PHONY: migrate
migrate: ## Apply migrations
	@sudo -u $(DEPLOYMENT_USER) bash -c 'source $(DEPLOYMENT_ROOT)/apps/pydeployer/releases/current/.env && \
		$(MANAGE_PY) migrate'

# ==================== Quick Setup ====================

.PHONY: quickstart
quickstart: ## Complete setup from scratch
	@echo "$(GREEN)Starting PyDeployer Quick Setup...$(NC)"
	@make setup-environment
	@make install-pydeployer
	@make configure-pydeployer
	@make init-database
	@make collectstatic
	@make register-self
	@echo ""
	@echo "$(GREEN)╔════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║   PyDeployer Setup Complete! 🚀            ║$(NC)"
	@echo "$(GREEN)╠════════════════════════════════════════════╣$(NC)"
	@echo "$(GREEN)║                                            ║$(NC)"
	@echo "$(GREEN)║   Next steps:                              ║$(NC)"
	@echo "$(GREEN)║   1. make create-superuser                 ║$(NC)"
	@echo "$(GREEN)║   2. make start                            ║$(NC)"
	@echo "$(GREEN)║   3. Access admin at http://localhost:8000 ║$(NC)"
	@echo "$(GREEN)║                                            ║$(NC)"
	@echo "$(GREEN)╚════════════════════════════════════════════╝$(NC)"

.PHONY: clean
clean: ## Clean up temporary files
	@echo "$(YELLOW)Cleaning up...$(NC)"
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@echo "$(GREEN)Cleanup complete!$(NC)"

# ==================== Help ====================

.DEFAULT_GOAL := help