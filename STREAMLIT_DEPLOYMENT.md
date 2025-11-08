# Streamlit Cloud Deployment Guide

This guide will help you deploy the FCR Dashboard to Streamlit Cloud (free) or other platforms.

## Prerequisites

1. GitHub account
2. Code pushed to a GitHub repository
3. Excel files ready (or use file upload feature)

## Quick Deployment to Streamlit Cloud

### Step 1: Prepare Your Repository

1. **Ensure your repository structure:**
   ```
   FCR_DASHBOARD/
   ├── FCR_DASHBOARD.py          # Main dashboard file
   ├── requirements.txt          # Python dependencies
   ├── .streamlit/
   │   └── config.toml          # Streamlit configuration
   ├── .gitignore               # Git ignore file
   └── README.md                # Documentation
   ```

2. **Commit and push to GitHub:**
   ```bash
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

### Step 2: Deploy to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with your GitHub account
3. Click **"New app"**
4. Fill in the details:
   - **Repository**: Select your repository
   - **Branch**: `main` (or your default branch)
   - **Main file path**: `FCR_DASHBOARD.py`
   - **App URL**: Choose a unique URL (e.g., `fcr-dashboard`)
5. Click **"Deploy"**

### Step 3: Configure Environment Variables (Optional)

If you want to use a custom data folder path:

1. Go to your app settings on Streamlit Cloud
2. Click **"Settings"** → **"Secrets"**
3. Add environment variable:
   ```toml
   DATA_FOLDER = "data"
   ```

### Step 4: Upload Data Files

**Option A: Use File Upload Feature**
- The dashboard includes a file uploader in the sidebar
- Upload Excel files directly through the web interface

**Option B: Add Files to Repository**
- Add Excel files to the `data/` folder in your repository
- Push to GitHub
- Files will be available after redeploy

**Option C: Use Cloud Storage (Advanced)**
- Set up AWS S3, Google Cloud Storage, or Azure Blob Storage
- Modify the code to read from cloud storage
- Update environment variables with credentials

## Deployment Checklist

- [ ] Code is pushed to GitHub
- [ ] `requirements.txt` is present and up-to-date
- [ ] `.streamlit/config.toml` is configured
- [ ] `.gitignore` excludes unnecessary files
- [ ] Data folder exists or file upload is configured
- [ ] Environment variables are set (if needed)
- [ ] App is deployed and accessible
- [ ] Tested with sample data

## Troubleshooting

### App Won't Start

1. **Check logs:**
   - Go to your app on Streamlit Cloud
   - Click **"Manage app"** → **"Logs"**
   - Look for error messages

2. **Common issues:**
   - Missing dependencies in `requirements.txt`
   - Syntax errors in Python code
   - Missing data folder (should be created automatically)
   - Port configuration issues

### Files Not Loading

1. **Check file paths:**
   - Ensure files are in the `data/` folder
   - Check file naming convention (YYYYMMDD format)
   - Verify file format (.xlsx)

2. **Check permissions:**
   - Files should be readable
   - Data folder should be writable (for uploads)

### Performance Issues

1. **Optimize caching:**
   - Cache TTL is set to 300 seconds (5 minutes)
   - Adjust in code if needed

2. **Reduce data size:**
   - Limit number of files loaded
   - Filter data before processing

## Alternative Deployment Platforms

### Railway.app

1. Sign up at [railway.app](https://railway.app)
2. Create new project from GitHub
3. Add persistent volume for `data/` folder
4. Deploy!

### Render.com

1. Sign up at [render.com](https://render.com)
2. Create new Web Service
3. Connect GitHub repository
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `streamlit run FCR_DASHBOARD.py --server.port=$PORT --server.address=0.0.0.0`
6. Deploy!

### Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "FCR_DASHBOARD.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Build and run:
```bash
docker build -t fcr-dashboard .
docker run -p 8501:8501 fcr-dashboard
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATA_FOLDER` | Path to data folder | `data` |
| `PORT` | Server port | `8501` |

## Security Considerations

1. **Authentication:**
   - Add password protection using `streamlit-authenticator`
   - Or use OAuth (Google, Microsoft)

2. **File Validation:**
   - Validate uploaded files
   - Check file size limits
   - Verify file format

3. **Data Privacy:**
   - Use HTTPS (automatically provided by Streamlit Cloud)
   - Encrypt sensitive data
   - Secure file storage

## Support

For issues or questions:
1. Check the [Streamlit documentation](https://docs.streamlit.io)
2. Review deployment platform documentation
3. Check application logs
4. Review error messages in the dashboard

## Next Steps

After deployment:
1. Test with sample data
2. Configure file upload (if needed)
3. Set up automated backups
4. Monitor performance
5. Add authentication (if needed)

