#!/bin/bash
# PostgreSQL Installation Script for Ubuntu LTS
# PyDeployer - Deployment Orchestration System

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}PostgreSQL Installation Script for Ubuntu${NC}"
echo "=========================================="

# Detect Ubuntu version
UBUNTU_VERSION=$(lsb_release -rs)
UBUNTU_CODENAME=$(lsb_release -cs)

echo -e "${GREEN}Detected Ubuntu ${UBUNTU_VERSION} (${UBUNTU_CODENAME})${NC}"

# Update package list
echo -e "${YELLOW}Updating package list...${NC}"
sudo apt-get update -qq

# Install prerequisites
echo -e "${YELLOW}Installing prerequisites...${NC}"
sudo apt-get install -y wget ca-certificates gnupg lsb-release

# Add PostgreSQL official repository
echo -e "${YELLOW}Adding PostgreSQL official repository...${NC}"
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'

# Add repository signing key
echo -e "${YELLOW}Adding PostgreSQL signing key...${NC}"
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list

# Update package list again
echo -e "${YELLOW}Updating package list with PostgreSQL repository...${NC}"
sudo apt-get update -qq

# Get latest stable PostgreSQL version
POSTGRES_VERSION=$(apt-cache search postgresql-[0-9] | grep -E "^postgresql-[0-9]+ " | sort -V | tail -1 | cut -d' ' -f1 | sed 's/postgresql-//')

echo -e "${GREEN}Installing PostgreSQL ${POSTGRES_VERSION}...${NC}"

# Install PostgreSQL and contrib package
sudo apt-get install -y postgresql-${POSTGRES_VERSION} postgresql-contrib-${POSTGRES_VERSION} postgresql-client-${POSTGRES_VERSION}

# Install additional useful packages
echo -e "${YELLOW}Installing additional PostgreSQL packages...${NC}"
sudo apt-get install -y postgresql-server-dev-${POSTGRES_VERSION} libpq-dev

# Start and enable PostgreSQL service
echo -e "${YELLOW}Starting PostgreSQL service...${NC}"
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Configure PostgreSQL for local development
echo -e "${YELLOW}Configuring PostgreSQL...${NC}"

# Set password for postgres user (optional)
# sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"

# Configure pg_hba.conf for local connections
PG_VERSION_SHORT=$(echo ${POSTGRES_VERSION} | cut -d. -f1)
PG_CONFIG_DIR="/etc/postgresql/${POSTGRES_VERSION}/main"

# Backup original configuration
sudo cp ${PG_CONFIG_DIR}/postgresql.conf ${PG_CONFIG_DIR}/postgresql.conf.backup
sudo cp ${PG_CONFIG_DIR}/pg_hba.conf ${PG_CONFIG_DIR}/pg_hba.conf.backup

# Allow local connections
echo -e "${YELLOW}Configuring local connections...${NC}"
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = 'localhost'/" ${PG_CONFIG_DIR}/postgresql.conf

# Restart PostgreSQL to apply changes
echo -e "${YELLOW}Restarting PostgreSQL...${NC}"
sudo systemctl restart postgresql

# Verify installation
echo -e "${GREEN}Verifying PostgreSQL installation...${NC}"
sudo -u postgres psql --version

# Check service status
if systemctl is-active --quiet postgresql; then
    echo -e "${GREEN}✓ PostgreSQL is running${NC}"
else
    echo -e "${RED}✗ PostgreSQL is not running${NC}"
    exit 1
fi

# Display connection information
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  PostgreSQL ${POSTGRES_VERSION} Installation Complete! 🎉          ║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                        ║${NC}"
echo -e "${GREEN}║  Service Status: Active ✓                             ║${NC}"
echo -e "${GREEN}║  Config Dir: ${PG_CONFIG_DIR}                          ║${NC}"
echo -e "${GREEN}║  Data Dir: /var/lib/postgresql/${POSTGRES_VERSION}/main        ║${NC}"
echo -e "${GREEN}║                                                        ║${NC}"
echo -e "${GREEN}║  Default Superuser: postgres                          ║${NC}"
echo -e "${GREEN}║  Default Port: 5432                                   ║${NC}"
echo -e "${GREEN}║                                                        ║${NC}"
echo -e "${GREEN}║  To create a database:                                ║${NC}"
echo -e "${GREEN}║  sudo -u postgres createdb mydb                       ║${NC}"
echo -e "${GREEN}║                                                        ║${NC}"
echo -e "${GREEN}║  To access PostgreSQL shell:                          ║${NC}"
echo -e "${GREEN}║  sudo -u postgres psql                                ║${NC}"
echo -e "${GREEN}║                                                        ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""