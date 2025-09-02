#!/bin/bash
# Run database migrations

set -e

# Load environment variables
source /srv/deployments/apps/pydeployer/releases/current/.env

cd /srv/deployments/apps/pydeployer/releases/current

echo "Migrating Django built-in apps..."
/srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py migrate contenttypes
/srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py migrate auth
/srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py migrate admin
/srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py migrate sessions
/srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py migrate authtoken

echo "Migrating PyDeployer apps..."
/srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py migrate core

echo "All migrations applied!"