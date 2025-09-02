#!/bin/bash
# Configure Git for deploy user

set -e

DEPLOY_USER="deploy"

echo "Configuring Git for $DEPLOY_USER..."

# Change to deploy user's home directory to avoid permission issues
cd /home/$DEPLOY_USER

# Set Git global config for deploy user
sudo -u $DEPLOY_USER git config --global user.name "PyDeployer"
sudo -u $DEPLOY_USER git config --global user.email "deploy@pydeployer.local"
sudo -u $DEPLOY_USER git config --global init.defaultBranch main

# Configure Git to use SSH instead of HTTPS for GitLab
sudo -u $DEPLOY_USER git config --global url."git@gitlab.com:".insteadOf "https://gitlab.com/"

echo "Git configured for $DEPLOY_USER"

# Show the configuration
echo "Current Git configuration for $DEPLOY_USER:"
sudo -u $DEPLOY_USER git config --global --list