#!/bin/bash
# =============================================================================
# ArtBridge EC2 Setup Script
# Run this ONCE after SSH-ing into your EC2 Ubuntu instance.
#
# Usage:
#   chmod +x server_setup.sh
#   ./server_setup.sh
# =============================================================================

set -e  # Exit immediately if any command fails

echo ""
echo "=============================================="
echo "  ArtBridge EC2 Server Setup"
echo "=============================================="
echo ""

# ── 1. Update system packages ─────────────────────────────────────────────────
echo "[1/8] Updating system packages..."
sudo apt update -y && sudo apt upgrade -y

# ── 2. Install required tools ─────────────────────────────────────────────────
echo "[2/8] Installing Python, Nginx, Git..."
sudo apt install -y python3-pip python3-venv nginx git sqlite3

# ── 3. Clone the project ──────────────────────────────────────────────────────
echo "[3/8] Setting up project directory..."
# If you are uploading files via SCP instead of git clone,
# skip this block and just ensure your files are at /home/ubuntu/artbridge/
#
# To clone from GitHub, uncomment and edit the line below:
# git clone https://github.com/YOUR_USERNAME/artbridge.git /home/ubuntu/artbridge

# For now, create the directory if it doesn't exist
mkdir -p /home/ubuntu/artbridge/backend

echo "  >> If you haven't uploaded your files yet, run from your local machine:"
echo "     scp -r -i your-key.pem c:/ArtBridge/backend/ ubuntu@YOUR_EC2_IP:/home/ubuntu/artbridge/"
echo ""

# ── 4. Set up Python virtual environment ─────────────────────────────────────
echo "[4/8] Creating Python virtual environment..."
cd /home/ubuntu/artbridge/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "  >> Python environment ready."

# ── 5. Create the uploads directory ──────────────────────────────────────────
echo "[5/8] Creating upload directories..."
mkdir -p /home/ubuntu/artbridge/backend/static/uploads
chmod 755 /home/ubuntu/artbridge/backend/static/uploads

# ── 6. Initialise the SQLite database ────────────────────────────────────────
echo "[6/8] Initialising database..."
cd /home/ubuntu/artbridge/backend
source venv/bin/activate
python3 -c "from db import init_db; init_db(); print('  >> Database initialised.')"

# ── 7. Install and enable the Gunicorn systemd service ───────────────────────
echo "[7/8] Installing Gunicorn systemd service..."
sudo cp /home/ubuntu/artbridge/backend/deploy/artbridge.service /etc/systemd/system/artbridge.service
sudo systemctl daemon-reload
sudo systemctl enable artbridge
sudo systemctl start artbridge
echo "  >> Gunicorn service started."

# ── 8. Configure Nginx ───────────────────────────────────────────────────────
echo "[8/8] Configuring Nginx..."
sudo cp /home/ubuntu/artbridge/backend/deploy/artbridge.nginx /etc/nginx/sites-available/artbridge
sudo ln -sf /etc/nginx/sites-available/artbridge /etc/nginx/sites-enabled/artbridge
sudo rm -f /etc/nginx/sites-enabled/default   # remove default placeholder
sudo nginx -t && sudo systemctl restart nginx
echo "  >> Nginx configured and restarted."

echo ""
echo "=============================================="
echo "  Setup Complete!"
echo "=============================================="
echo ""
echo "  Your app should now be running at:"
echo "  http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo ""
echo "  To check service status:"
echo "    sudo systemctl status artbridge"
echo "    sudo journalctl -u artbridge -f"
echo ""
echo "  To add a domain name later:"
echo "    1. Point your domain's A record to this IP."
echo "    2. Edit /etc/nginx/sites-available/artbridge and add 'server_name yourdomain.com'"
echo "    3. Run: sudo certbot --nginx -d yourdomain.com"
echo ""
