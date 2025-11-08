# Google Drive Integration Setup Guide

## ✅ What You Have Ready

- **Folder ID**: `YOUR_GOOGLE_DRIVE_FOLDER_ID_HERE`
- **Service Account JSON**: Already created
- **Google Drive Folder**: Already shared with service account

## 📋 Next Steps - Streamlit Cloud Configuration

### Step 1: Prepare Your JSON Credentials

You already have the JSON file content. We'll use it in Streamlit Cloud secrets.

### Step 2: Set Up Streamlit Cloud Secrets

1. **Go to Streamlit Cloud**
   - Visit: https://share.streamlit.io
   - Sign in with your GitHub account

2. **Create/Select Your App**
   - Click "New app" or select existing app
   - Connect your GitHub repository

3. **Add Secrets**
   - Click "⚙️ Settings" (gear icon)
   - Click "Secrets" in the left menu
   - Add these secrets (click "Add new secret" for each):

**Secret 1:**
```
GOOGLE_DRIVE_FOLDER_ID
```
Value: `YOUR_GOOGLE_DRIVE_FOLDER_ID_HERE` (replace with your actual Google Drive folder ID)

**Secret 2:**
```
GOOGLE_APPLICATION_CREDENTIALS_JSON
```
Value: (Paste your entire JSON file content here - all of it, including the curly braces)
```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "YOUR_PRIVATE_KEY_ID_HERE",
  "private_key": "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_CONTENT_HERE\n-----END PRIVATE KEY-----\n",
  "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
  "client_id": "YOUR_CLIENT_ID_HERE",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
```

**⚠️ IMPORTANT**: Replace all placeholder values with your actual service account credentials from Google Cloud Console.

### Step 3: Verify Folder Sharing

Make sure your Google Drive folder is shared with:
- **Email**: `your-service-account@your-project.iam.gserviceaccount.com` (use your actual service account email)
- **Permission**: Editor

**How to check:**
1. Go to your Google Drive folder
2. Right-click → "Share"
3. Check if the service account email is in the list
4. If not, add it with "Editor" permission

### Step 4: Test Locally (Optional)

Before deploying to Streamlit Cloud, you can test locally:

1. Create a file named `.streamlit/secrets.toml` in your project folder
2. Add this content:
```toml
GOOGLE_DRIVE_FOLDER_ID = "YOUR_GOOGLE_DRIVE_FOLDER_ID_HERE"
GOOGLE_APPLICATION_CREDENTIALS_JSON = '''{
  "type": "service_account",
  "project_id": "your-project-id",
  ... (paste your full JSON credentials here)
}'''
```

**⚠️ IMPORTANT**: Replace all placeholder values with your actual credentials.

3. Run: `streamlit run FCR_DASHBOARD_GOOGLE_DRIVE.py`

### Step 5: Deploy to Streamlit Cloud

1. **Push code to GitHub**
   ```bash
   git add .
   git commit -m "Add Google Drive integration"
   git push
   ```

2. **Deploy on Streamlit Cloud**
   - Go to share.streamlit.io
   - Select your repository
   - Main file: `FCR_DASHBOARD_GOOGLE_DRIVE.py`
   - Click "Deploy"

3. **Wait for deployment**
   - First deployment takes 2-3 minutes
   - Check for any errors in the logs

### Step 6: Test File Upload

1. Open your deployed dashboard
2. Look for "📤 Upload Excel Files" in the sidebar
3. Upload a test Excel file
4. Check if it appears in your Google Drive folder
5. Verify the dashboard shows the data

## 🎯 Daily Usage

### Option 1: Upload via Dashboard (Recommended)
1. Open the dashboard
2. Go to sidebar → "📤 Upload Excel Files"
3. Click "Browse files" or drag and drop
4. Select your Excel file
5. File automatically uploads to Google Drive
6. Dashboard refreshes automatically

### Option 2: Upload Directly to Google Drive
1. Go to your Google Drive folder
2. Drag and drop Excel file into the folder
3. Open the dashboard
4. Click "🔄 Reload Data" button
5. Dashboard will show the new file

## ❓ Troubleshooting

### Problem: "Google Drive not configured"
**Solution**: Check that secrets are set correctly in Streamlit Cloud

### Problem: "Permission denied"
**Solution**: Make sure folder is shared with service account email

### Problem: Files not showing
**Solution**: 
1. Check file format (.xlsx or .xls)
2. Check filename contains date (YYYYMMDD format)
3. Click "Reload Data" button
4. Check Google Drive folder directly

### Problem: Upload fails
**Solution**:
1. Check file size (must be under 50MB)
2. Check file format (.xlsx or .xls)
3. Verify folder permissions
4. Check Streamlit Cloud logs for errors

## 📞 Need Help?

If you encounter issues:
1. Check Streamlit Cloud logs (Settings → Logs)
2. Verify secrets are set correctly
3. Check Google Drive folder permissions
4. Make sure service account email matches

## ✅ Checklist

Before deploying, make sure:
- [ ] Google Drive folder created
- [ ] Folder ID copied
- [ ] Service account created
- [ ] JSON credentials downloaded
- [ ] Folder shared with service account
- [ ] Secrets added to Streamlit Cloud
- [ ] Code pushed to GitHub
- [ ] App deployed on Streamlit Cloud

## 🎉 You're All Set!

Once deployed, you can:
- Upload Excel files daily through the dashboard
- Files stored securely in Google Drive
- Access files from anywhere
- Multiple users can upload files
- Files persist forever (not lost on app restart)

