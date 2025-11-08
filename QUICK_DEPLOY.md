# Quick Deployment Guide

## Option 1: Streamlit Cloud (Free - Recommended for Start)

### Steps:

1. **Create GitHub Repository**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/fcr-dashboard.git
   git push -u origin main
   ```

2. **Deploy on Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Click "New app"
   - Select your repository
   - Main file path: `FCR_DASHBOARD_WITH_UPLOAD.py`
   - Click "Deploy!"

3. **Upload Files Daily**
   - Use the file uploader in the sidebar
   - Upload Excel files through the web interface
   - Files will be stored in the app's temporary storage

**Note:** Files may be lost on app restart. For persistent storage, use Option 2.

---

## Option 2: Railway (Persistent Storage - $5-10/month)

### Steps:

1. **Sign up at Railway**
   - Go to [railway.app](https://railway.app)
   - Sign up with GitHub

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Select your repository

3. **Configure Environment**
   - Add environment variable: `PORT=8501`
   - Railway will auto-detect Python and install dependencies

4. **Add Persistent Volume** (for data folder)
   - Go to "Volumes" tab
   - Create volume: `/app/data`
   - Mount to: `data` folder

5. **Deploy**
   - Railway will automatically deploy
   - Get your app URL

6. **Upload Files**
   - Use file uploader in sidebar
   - Files persist in the volume

---

## Option 3: Render.com (Free Tier Available)

### Steps:

1. **Sign up at Render**
   - Go to [render.com](https://render.com)
   - Sign up with GitHub

2. **Create Web Service**
   - Click "New" → "Web Service"
   - Connect your GitHub repository

3. **Configure Service**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `streamlit run FCR_DASHBOARD_WITH_UPLOAD.py --server.port=$PORT --server.address=0.0.0.0`
   - Environment: Python 3
   - Plan: Free (or paid for persistent disk)

4. **Deploy**
   - Click "Create Web Service"
   - Wait for deployment

5. **Set up Persistent Disk** (Paid plans only)
   - Go to "Disks" tab
   - Create disk: `/opt/render/project/src/data`
   - Mount to data folder

---

## Option 4: Self-Hosted VPS

### Steps:

1. **Set up VPS** (DigitalOcean, Linode, etc.)
   - Create Ubuntu 20.04/22.04 droplet
   - SSH into server

2. **Install Dependencies**
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv nginx
   ```

3. **Set up Application**
   ```bash
   mkdir -p /var/www/fcr-dashboard
   cd /var/www/fcr-dashboard
   git clone YOUR_REPO_URL .
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Create Systemd Service**
   ```bash
   sudo nano /etc/systemd/system/fcr-dashboard.service
   ```
   Content:
   ```ini
   [Unit]
   Description=FCR Dashboard
   After=network.target

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/var/www/fcr-dashboard
   Environment="PATH=/var/www/fcr-dashboard/venv/bin"
   ExecStart=/var/www/fcr-dashboard/venv/bin/streamlit run FCR_DASHBOARD_WITH_UPLOAD.py --server.port=8501 --server.address=0.0.0.0
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

5. **Start Service**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable fcr-dashboard
   sudo systemctl start fcr-dashboard
   ```

6. **Set up Nginx Reverse Proxy**
   ```bash
   sudo nano /etc/nginx/sites-available/fcr-dashboard
   ```
   Content:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://localhost:8501;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
   ```bash
   sudo ln -s /etc/nginx/sites-available/fcr-dashboard /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

7. **Set up SSL** (Let's Encrypt)
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```

---

## File Upload Methods

### Method 1: Web Interface (Built-in)
- Use the file uploader in the sidebar
- Upload files directly through the browser
- Best for: Manual daily uploads

### Method 2: Automated Upload Script
Create `upload_file.py`:
```python
import requests
import sys

def upload_file(file_path, dashboard_url):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(f'{dashboard_url}/upload', files=files)
    return response.status_code == 200

if __name__ == '__main__':
    file_path = sys.argv[1]
    dashboard_url = sys.argv[2]
    upload_file(file_path, dashboard_url)
```

### Method 3: Cloud Storage Integration
- Upload files to S3/GCS
- App reads from cloud storage automatically
- Best for: Automated, production use

---

## Troubleshooting

### Files Not Persisting (Streamlit Cloud)
- Use Railway or Render with persistent storage
- Or integrate with cloud storage (S3, GCS)

### App Not Starting
- Check logs for errors
- Verify all dependencies in requirements.txt
- Check port configuration

### File Upload Not Working
- Check file size limits (default: 50MB)
- Verify file format (.xlsx, .xls)
- Check folder permissions

### Performance Issues
- Increase cache TTL
- Optimize data processing
- Use database for large datasets

---

## Support

For issues or questions:
1. Check the deployment platform's documentation
2. Review Streamlit documentation
3. Check application logs

