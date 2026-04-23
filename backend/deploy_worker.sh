#!/bin/bash
# LinkConnect Worker - Oracle Cloud Setup Script
# Run this on the Oracle Cloud VM after SSH-ing in

set -e

echo "=== LinkConnect Worker Setup ==="

# 1. Update system
sudo apt-get update -y && sudo apt-get upgrade -y

# 2. Install Python 3.11 and pip
sudo apt-get install -y python3 python3-pip python3-venv git curl wget

# 3. Install Playwright system dependencies
sudo apt-get install -y \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 libx11-6 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libxshmfence1 libgles2 fonts-liberation \
    libvulkan1 xdg-utils

# 4. Clone the repo
cd ~
if [ -d "linkconnect" ]; then
    cd linkconnect && git pull
else
    git clone https://github.com/rsrihari-arch/linkconnect.git
    cd linkconnect
fi

# 5. Set up Python venv
cd backend
python3 -m venv venv
source venv/bin/activate

# 6. Install Python dependencies
pip install fastapi uvicorn sqlalchemy pg8000 python-jose passlib bcrypt playwright python-dotenv cryptography

# 7. Install Playwright browsers
playwright install chromium

# 8. Create .env file
cat > .env << 'ENVEOF'
DATABASE_URL=postgresql://neondb_owner:npg_gmMVTb8P1rsZ@ep-soft-sunset-am5twvsh.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require
ENCRYPTION_KEY=linkconnect-secret-2024
SECRET_KEY=linkconnect-app-secret
ENVEOF

echo "=== Setup complete! ==="
echo "Start worker with: cd ~/linkconnect/backend && source venv/bin/activate && nohup python3 -u worker.py > /tmp/worker.log 2>&1 &"
