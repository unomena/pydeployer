#!/bin/bash
# Cleanup stuck deployment for a project/environment

set -e

PROJECT=$1
ENV=$2

if [ -z "$PROJECT" ] || [ -z "$ENV" ]; then
    echo "Usage: $0 PROJECT ENV"
    echo "Example: $0 pydeployer prod"
    exit 1
fi

# Load environment variables
source /srv/deployments/apps/pydeployer/releases/current/.env

# Run the cleanup command
cd /srv/deployments/apps/pydeployer/releases/current
/srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py cleanup_deployment "$PROJECT" "$ENV"