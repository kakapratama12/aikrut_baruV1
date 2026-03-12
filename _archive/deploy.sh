#!/bin/bash
# =============================================================
# Aikrut Deployment Script
# =============================================================
# Usage:
#   Local dev:  ./deploy.sh
#   Production: ./deploy.sh --prod
# =============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Aikrut Deployment Script${NC}"
echo -e "${BLUE}========================================${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    echo "Install Docker: https://docs.docker.com/engine/install/"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not available.${NC}"
    echo "Docker Compose should be included with modern Docker installations."
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose found${NC}"

# Create .env if missing
if [ ! -f .env ]; then
    echo -e "${YELLOW}No .env file found. Creating from .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠ Please review .env and update values (especially secrets for production)${NC}"
fi

# Determine mode
PROD_MODE=false
COMPOSE_FILES="-f docker-compose.yml"

if [ "$1" = "--prod" ] || [ "$1" = "-p" ]; then
    PROD_MODE=true
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
    echo -e "${BLUE}Mode: PRODUCTION${NC}"

    # Check if domain is set
    source .env
    if [ -z "$DOMAIN" ] || [ "$DOMAIN" = "yourdomain.com" ]; then
        echo -e "${RED}Error: DOMAIN is not set in .env${NC}"
        echo "Set DOMAIN=yourdomain.com in .env before deploying to production."
        exit 1
    fi

    # Replace domain placeholder in nginx prod config
    sed -i "s/YOUR_DOMAIN/$DOMAIN/g" nginx/nginx.prod.conf 2>/dev/null || \
    sed -i '' "s/YOUR_DOMAIN/$DOMAIN/g" nginx/nginx.prod.conf

    # SSL certificate setup
    if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
        echo -e "${YELLOW}Setting up SSL certificate for $DOMAIN...${NC}"
        docker run --rm \
            -v /etc/letsencrypt:/etc/letsencrypt \
            -p 80:80 \
            certbot/certbot certonly \
            --standalone \
            --non-interactive \
            --agree-tos \
            --email "${SSL_EMAIL:-admin@$DOMAIN}" \
            -d "$DOMAIN"
    fi
else
    echo -e "${BLUE}Mode: LOCAL DEVELOPMENT${NC}"
fi

# Build and start
echo -e "\n${BLUE}Building and starting services...${NC}"
docker compose $COMPOSE_FILES up -d --build

# Wait for health checks
echo -e "\n${BLUE}Waiting for services to start...${NC}"
sleep 5

# Check status
echo -e "\n${BLUE}Service Status:${NC}"
docker compose $COMPOSE_FILES ps

# Print access info
echo -e "\n${GREEN}========================================${NC}"
if [ "$PROD_MODE" = true ]; then
    echo -e "${GREEN}  Aikrut is running at https://$DOMAIN${NC}"
else
    echo -e "${GREEN}  Aikrut is running!${NC}"
    echo -e "${GREEN}  Frontend:  http://localhost:3000${NC}"
    echo -e "${GREEN}  Backend:   http://localhost:8000${NC}"
    echo -e "${GREEN}  API Docs:  http://localhost:8000/docs${NC}"
    echo -e "${GREEN}  MongoDB:   mongodb://localhost:27017${NC}"
fi
echo -e "${GREEN}========================================${NC}"
echo -e "\n${BLUE}Useful commands:${NC}"
echo "  docker compose logs -f          # View logs"
echo "  docker compose down             # Stop all services"
echo "  docker compose up -d --build    # Rebuild and restart"
