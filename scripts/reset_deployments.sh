#!/bin/bash
# Reset all deployments for a project

set -e

PROJECT=$1

if [ -z "$PROJECT" ]; then
    echo "Usage: $0 PROJECT"
    echo "Example: $0 pydeployer"
    exit 1
fi

# Load environment variables
source /srv/deployments/apps/pydeployer/releases/current/.env

# Run the reset command
cd /srv/deployments/apps/pydeployer/releases/current
/srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py reset_deployments "$PROJECT"