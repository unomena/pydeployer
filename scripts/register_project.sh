#!/bin/bash
# Register a new project

set -e

NAME=$1
REPO=$2
PORT=$3

if [ -z "$NAME" ] || [ -z "$REPO" ] || [ -z "$PORT" ]; then
    echo "Usage: $0 NAME REPO PORT"
    echo "Example: $0 myapp git@gitlab.com:org/repo.git 8100"
    exit 1
fi

# Load environment variables
source /srv/deployments/apps/pydeployer/releases/current/.env

# Run the register command
cd /srv/deployments/apps/pydeployer/releases/current
/srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py register_project "$NAME" --repo="$REPO" --port-start="$PORT"