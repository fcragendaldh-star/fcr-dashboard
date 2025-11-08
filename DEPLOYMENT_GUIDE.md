# FCR Dashboard Deployment Guide

This guide covers deployment options for the FCR Dashboard with daily Excel file upload capabilities.

## Deployment Options Overview

### 🟢 **Recommended: Streamlit Cloud (Free)**
**Best for**: Quick deployment, low cost, easy setup

**Pros:**
- ✅ Free forever (with limitations)
- ✅ Easy deployment from GitHub
- ✅ Automatic HTTPS
- ✅ Built-in file upload support via Streamlit
- ✅ No server management

**Cons:**
- ⚠️ File storage is ephemeral (resets on redeploy)
- ⚠️ Limited to 1GB RAM
- ⚠️ Files stored in session/temporary storage
- ⚠️ Need GitHub account

**Setup Steps:**
1. Push code to GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect GitHub account
4. Select repository and main file
5. Deploy!

**File Upload Strategy:**
- Use Streamlit's file uploader (built into enhanced version)
- Files stored in session state or temporary directory
- Consider cloud storage (S3, Google Drive) for persistence

---

### 🟡 **Streamlit Cloud + Cloud Storage (Recommended for Production)**
**Best for**: Production use with persistent file storage

**Architecture:**
- Deploy app on Streamlit Cloud (free)
- Store Excel files in cloud storage:
  - AWS S3
  - Google Cloud Storage
  - Azure Blob Storage
  - Google Drive API

**Pros:**
- ✅ Free hosting (Streamlit Cloud)
- ✅ Persistent file storage
- ✅ Scalable
- ✅ Can automate file uploads via API

**Setup:**
1. Deploy on Streamlit Cloud
2. Set up cloud storage bucket
3. Modify app to read from cloud storage
4. Upload files daily to cloud storage

---

### 🟢 **Railway.app (Easy & Affordable)**
**Best for**: Simple deployment with persistent storage

**Pros:**
- ✅ Easy deployment
- ✅ Persistent file storage
- ✅ Free tier: $5 credit/month
- ✅ Paid: ~$5-10/month
- ✅ Automatic HTTPS
- ✅ Supports file uploads

**Setup Steps:**
1. Sign up at [railway.app](https://railway.app)
2. Create new project
3. Connect GitHub repository
4. Add persistent volume for data folder
5. Deploy!

**Cost:** ~$5-10/month after free credit

---

### 🟡 **Render.com (Free Tier Available)**
**Best for**: Free hosting with limitations

**Pros:**
- ✅ Free tier available
- ✅ Persistent disk storage (paid plans)
- ✅ Easy deployment from GitHub
- ✅ Automatic HTTPS

**Cons:**
- ⚠️ Free tier: Spins down after inactivity
- ⚠️ Limited disk space on free tier
- ⚠️ Slow cold starts on free tier

**Cost:** Free (with limitations) or $7/month for web service

---

### 🟡 **AWS EC2 (Full Control)**
**Best for**: Maximum control, enterprise use

**Pros:**
- ✅ Full control over environment
- ✅ Persistent storage
- ✅ Scalable
- ✅ Can set up automated backups

**Cons:**
- ⚠️ Requires server management
- ⚠️ More complex setup
- ⚠️ Costs: ~$10-50/month

**Setup Steps:**
1. Launch EC2 instance (Ubuntu/Debian)
2. Install Python, Streamlit
3. Set up Nginx reverse proxy
4. Configure SSL certificate
5. Set up file upload mechanism
6. Configure automatic startup

---

### 🟡 **DigitalOcean App Platform**
**Best for**: Simple PaaS with good performance

**Pros:**
- ✅ Easy deployment
- ✅ Persistent storage
- ✅ Good performance
- ✅ Auto-scaling

**Cons:**
- ⚠️ Costs: $5-12/month minimum
- ⚠️ Limited free tier

**Cost:** $5-12/month

---

### 🟡 **Google Cloud Run (Serverless)**
**Best for**: Pay-per-use, serverless architecture

**Pros:**
- ✅ Pay only for usage
- ✅ Auto-scaling
- ✅ Good for low traffic
- ✅ Can use Cloud Storage for files

**Cons:**
- ⚠️ Cold starts
- ⚠️ Requires containerization (Docker)
- ⚠️ More complex setup

**Cost:** Pay-per-use (~$0-10/month for low traffic)

---

### 🟢 **Self-Hosted on VPS (Most Flexible)**
**Best for**: Complete control, existing infrastructure

**Options:**
- DigitalOcean Droplet ($4-6/month)
- Linode ($5/month)
- Vultr ($2.50-6/month)
- Hetzner Cloud (€4/month)

**Pros:**
- ✅ Full control
- ✅ Persistent storage
- ✅ Can set up custom domain
- ✅ Affordable

**Cons:**
- ⚠️ Requires server management
- ⚠️ Need to set up SSL, security
- ⚠️ Manual updates

---

## File Upload Methods

### Option 1: Streamlit File Uploader (Built-in)
- Users upload files through the web interface
- Files stored in session/temp directory
- Best for: Small files, occasional uploads
- **Implementation:** See enhanced version with file uploader

### Option 2: Cloud Storage Integration
- Upload files to S3/GCS/Azure
- App reads from cloud storage
- Best for: Production, automated uploads
- **Implementation:** Use boto3 (AWS) or google-cloud-storage

### Option 3: FTP/SFTP Server
- Set up FTP server
- Upload files via FTP client
- App reads from shared directory
- Best for: Enterprise, existing infrastructure

### Option 4: Google Drive Integration
- Upload to Google Drive
- App reads via Google Drive API
- Best for: Teams using Google Workspace
- **Implementation:** Use PyDrive or google-api-python-client

### Option 5: Database Storage
- Store Excel data in database (PostgreSQL, MySQL)
- Upload Excel, parse and store in DB
- Best for: Large datasets, complex queries
- **Implementation:** Use pandas + SQLAlchemy

---

## Recommended Deployment Strategy

### For Quick Start (Free):
1. **Deploy on Streamlit Cloud** (free)
2. **Add file uploader** to the app (see enhanced version)
3. Upload files daily through web interface

### For Production:
1. **Deploy on Railway or Render** ($5-10/month)
2. **Set up cloud storage** (AWS S3 or Google Cloud Storage)
3. **Automate file uploads** via:
   - Python script with cloud storage SDK
   - Scheduled task (cron job)
   - Google Drive folder sync
   - API endpoint for file uploads

---

## Security Considerations

1. **Authentication**: Add password protection
   - Streamlit-authenticator
   - OAuth (Google, Microsoft)
   - Basic HTTP auth

2. **File Validation**: Validate uploaded files
   - File type checking
   - Size limits
   - Virus scanning (optional)

3. **Data Privacy**: 
   - Encrypt sensitive data
   - Use HTTPS
   - Secure file storage

---

## Next Steps

1. Choose deployment platform
2. Set up file upload mechanism
3. Configure authentication (if needed)
4. Set up monitoring and backups
5. Test deployment

For detailed setup instructions for each platform, see the respective documentation.

