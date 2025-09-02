#!/bin/bash
# Setup SSH key for deploy user

set -e

echo "Setting up SSH key for deploy user..."

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo: sudo $0"
    exit 1
fi

DEPLOY_USER="deploy"
SSH_DIR="/home/$DEPLOY_USER/.ssh"

# Create .ssh directory if it doesn't exist
sudo -u $DEPLOY_USER mkdir -p $SSH_DIR
chmod 700 $SSH_DIR

# Generate SSH key if it doesn't exist
if [ ! -f "$SSH_DIR/id_ed25519" ]; then
    echo "Generating new SSH key for $DEPLOY_USER..."
    sudo -u $DEPLOY_USER ssh-keygen -t ed25519 -C "deploy@pydeployer" -f "$SSH_DIR/id_ed25519" -N ""
    echo "SSH key generated successfully!"
else
    echo "SSH key already exists for $DEPLOY_USER"
fi

# Set correct permissions
chown -R $DEPLOY_USER:$DEPLOY_USER $SSH_DIR
chmod 600 $SSH_DIR/id_ed25519 2>/dev/null || true
chmod 644 $SSH_DIR/id_ed25519.pub 2>/dev/null || true

# Configure SSH to use the key for GitLab
CONFIG_FILE="$SSH_DIR/config"
if ! grep -q "gitlab.com" "$CONFIG_FILE" 2>/dev/null; then
    echo "Configuring SSH for GitLab..."
    cat >> "$CONFIG_FILE" << EOF

# GitLab
Host gitlab.com
    HostName gitlab.com
    User git
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking no
EOF
    chmod 600 "$CONFIG_FILE"
    chown $DEPLOY_USER:$DEPLOY_USER "$CONFIG_FILE"
fi

# Display the public key
echo ""
echo "========================================="
echo "SSH KEY SETUP COMPLETE!"
echo "========================================="
echo ""
echo "Add this SSH public key to your GitLab account:"
echo "(GitLab -> Settings -> SSH Keys)"
echo ""
echo "Key name: PyDeployer Deploy Key ($(hostname))"
echo ""
cat "$SSH_DIR/id_ed25519.pub"
echo ""
echo "========================================="
echo ""
echo "After adding the key to GitLab, you can test with:"
echo "sudo -u deploy ssh -T git@gitlab.com"
echo ""