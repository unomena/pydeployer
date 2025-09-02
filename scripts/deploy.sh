#!/bin/bash
# Deploy a project to an environment

set -e

PROJECT=$1
ENV=$2
COMMIT=$3

if [ -z "$PROJECT" ] || [ -z "$ENV" ]; then
    echo "Usage: $0 PROJECT ENV [COMMIT]"
    echo "Example: $0 myapp prod"
    echo "Example: $0 myapp staging abc123def"
    exit 1
fi

# Load environment variables
source /srv/deployments/apps/pydeployer/releases/current/.env

# Run the deployment command
cd /srv/deployments/apps/pydeployer/releases/current

if [ -z "$COMMIT" ]; then
    /srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py deploy "$PROJECT" --env="$ENV"
else
    /srv/deployments/apps/pydeployer/envs/prod/bin/python src/manage.py deploy "$PROJECT" --env="$ENV" --commit="$COMMIT"
fi