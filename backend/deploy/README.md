# ArtBridge Deployment Guide

## What's in this folder?

| File | Purpose |
|---|---|
| `server_setup.sh` | Run once on EC2 to install everything |
| `artbridge.service` | Systemd service — keeps the app alive 24/7 |
| `artbridge.nginx` | Nginx reverse proxy configuration |

---

## Step 1: Edit the service file

Before uploading, open `artbridge.service` and:

1. Replace `REPLACE_WITH_A_STRONG_RANDOM_SECRET_KEY` with a real secret.  
   Generate one by running on your local machine:
   ```
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **AWS Credentials** — choose ONE option:
   - ✅ **Recommended:** Attach an IAM Role to your EC2 instance with DynamoDB access (no keys needed).
   - Or uncomment the `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` lines and paste your keys.

---

## Step 2: Upload files to EC2

From your **Windows machine**, open PowerShell and run:

```powershell
# Replace your-key.pem and YOUR_EC2_IP with your values
scp -i "C:\path\to\your-key.pem" -r "C:\ArtBridge\backend" ubuntu@YOUR_EC2_IP:/home/ubuntu/artbridge/
```

---

## Step 3: SSH into your EC2 instance

```powershell
ssh -i "C:\path\to\your-key.pem" ubuntu@YOUR_EC2_IP
```

---

## Step 4: Run the setup script

```bash
cd /home/ubuntu/artbridge/backend/deploy
chmod +x server_setup.sh
./server_setup.sh
```

This will:
- Install Nginx, Python, Git
- Create a virtual environment and install dependencies
- Initialise the SQLite database
- Start the app as a background service
- Configure Nginx

---

## Step 5: Verify it's working

1. **Check service status:**
   ```bash
   sudo systemctl status artbridge
   ```
   Should show `Active (running)` in green.

2. **Visit your app:**
   Open your browser and go to:
   ```
   http://YOUR_EC2_IP
   ```

3. **View live logs:**
   ```bash
   sudo journalctl -u artbridge -f
   ```

---

## Step 6: Make sure EC2 Security Group allows traffic

In the AWS Console → EC2 → Security Groups → Edit Inbound Rules:

| Type | Protocol | Port | Source |
|---|---|---|---|
| SSH | TCP | 22 | Your IP |
| HTTP | TCP | 80 | 0.0.0.0/0 |
| HTTPS | TCP | 443 | 0.0.0.0/0 |

---

## Optional: Add a Domain Name Later

1. **Buy a domain** from [Namecheap](https://namecheap.com) or [Route 53](https://aws.amazon.com/route53/).

2. **Create an Elastic IP** in EC2 console (so your IP never changes) and associate it with your instance.

3. **Point your domain's A record** to your Elastic IP.

4. **Edit the Nginx config** on the server:
   ```bash
   sudo nano /etc/nginx/sites-available/artbridge
   # Change:  server_name _;
   # To:      server_name yourdomain.com www.yourdomain.com;
   sudo nginx -t && sudo systemctl reload nginx
   ```

5. **Install free SSL certificate** with Let's Encrypt:
   ```bash
   sudo apt install certbot python3-certbot-nginx -y
   sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
   ```
   Done! Your site will now have a green padlock 🔒

---

## Useful Commands

```bash
# Restart app
sudo systemctl restart artbridge

# Stop app
sudo systemctl stop artbridge

# View logs
sudo journalctl -u artbridge -n 100

# Test Nginx config
sudo nginx -t

# Reload Nginx after config changes
sudo systemctl reload nginx
```
