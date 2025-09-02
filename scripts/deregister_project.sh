#!/bin/bash
# Deregister a project

set -e

NAME=$1
FORCE=$2

if [ -z "$NAME" ]; then
    echo "Usage: $0 NAME [--force]"
    echo "Example: $0 myapp"
    echo "Example: $0 myapp --force  # Skip confirmation"
    exit 1
fi

# Load environment variables
source /srv/deployments/apps/pydeployer/releases/current/.env

# Run the deregister command
cd /srv/deployments/apps/pydeployer/releases/current

if [ "$FORCE" == "--force" ]; then
    /srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py deregister_project "$NAME" --force
else
    /srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py deregister_project "$NAME"
fi