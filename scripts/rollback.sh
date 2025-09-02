#!/bin/bash
# Rollback a deployment

set -e

PROJECT=$1
ENV=$2

if [ -z "$PROJECT" ] || [ -z "$ENV" ]; then
    echo "Usage: $0 PROJECT ENV"
    echo "Example: $0 myapp prod"
    exit 1
fi

# Load environment variables
source /srv/deployments/apps/pydeployer/releases/current/.env

# Run the rollback command
cd /srv/deployments/apps/pydeployer/releases/current
/srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py rollback "$PROJECT" --env="$ENV"