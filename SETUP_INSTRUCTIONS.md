# 🚀 Google Drive Integration - Complete Setup Instructions

## ✅ Step 1: Verify Your Setup (You've Already Done This!)

You have:
- ✅ Folder ID: `YOUR_GOOGLE_DRIVE_FOLDER_ID_HERE`
- ✅ JSON Credentials: Service account created
- ✅ Google Drive folder: Created and ready

**IMPORTANT:** Make sure your Google Drive folder is shared with the service account email:
- Email: `fcr-dashboard-service@fcr-dashboard.iam.gserviceaccount.com`
- Permission: **Editor**

### How to Share Folder:
1. Open your Google Drive folder
2. Right-click → "Share"
3. Paste the email: `fcr-dashboard-service@fcr-dashboard.iam.gserviceaccount.com`
4. Set permission to **Editor**
5. Uncheck "Notify people"
6. Click "Share"

---

## 📋 Step 2: Install Required Packages

Run this command in your terminal:

```bash
pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2
```

Or update your `requirements.txt` (already done for you).

---

## 🔐 Step 3: Configure Streamlit Cloud Secrets

### For Streamlit Cloud Deployment:

1. **Go to Streamlit Cloud**
   - Visit: https://share.streamlit.io
   - Sign in with GitHub

2. **Create New App or Select Existing**
   - Click "New app"
   - Connect your GitHub repository
   - Main file: `FCR_DASHBOARD_GOOGLE_DRIVE.py`

3. **Add Secrets**
   - Click "⚙️ Settings" → "Secrets"
   - Add these two secrets:

**Secret 1:**
```
GOOGLE_DRIVE_FOLDER_ID = "YOUR_GOOGLE_DRIVE_FOLDER_ID_HERE"
```

**Secret 2:**
Copy your entire JSON file content and paste it as:
```
GOOGLE_APPLICATION_CREDENTIALS_JSON = '{
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
}'

**⚠️ IMPORTANT**: Replace all placeholder values with your actual service account credentials from Google Cloud Console.
```

**Note:** Make sure the JSON is on a single line or properly formatted in the secrets file.

### For Local Testing:

Create a file `.streamlit/secrets.toml` in your project folder:

```toml
GOOGLE_DRIVE_FOLDER_ID = "YOUR_GOOGLE_DRIVE_FOLDER_ID_HERE"
GOOGLE_APPLICATION_CREDENTIALS_JSON = '''{
  "type": "service_account",
  "project_id": "your-project-id",
  ...
  (paste your full JSON credentials here)
}'''
```

**⚠️ IMPORTANT**: Replace all placeholder values with your actual credentials.

---

## 🚀 Step 4: Deploy Your App

1. **Push code to GitHub:**
   ```bash
   git add .
   git commit -m "Add Google Drive integration"
   git push
   ```

2. **Deploy on Streamlit Cloud:**
   - Go to share.streamlit.io
   - Select your repository
   - Main file: `FCR_DASHBOARD_GOOGLE_DRIVE.py`
   - Click "Deploy"

3. **Wait for deployment** (2-3 minutes)

---

## 📤 Step 5: Test File Upload

### Option 1: Upload via Dashboard
1. Open your deployed dashboard
2. Look in the sidebar for "📤 Upload Excel Files"
3. Click "Browse files" or drag and drop
4. Select your Excel file
5. File automatically uploads to Google Drive
6. Dashboard refreshes automatically

### Option 2: Upload Directly to Google Drive
1. Go to your Google Drive folder
2. Drag and drop Excel file
3. Open the dashboard
4. Click "🔄 Reload Data" button

---

## ✅ What You'll See

1. **In the Sidebar:**
   - "📤 Upload Excel Files" section at the top
   - File upload widget
   - Status messages when uploading

2. **In the Dashboard:**
   - All data from Google Drive files
   - Automatic refresh after upload
   - Same beautiful dashboard as before

---

## ❓ Troubleshooting

### Problem: "Google Drive not configured"
**Solution:** Check that secrets are set correctly in Streamlit Cloud

### Problem: "Permission denied"
**Solution:** Make sure folder is shared with service account email

### Problem: Files not showing
**Solution:**
1. Check file format (.xlsx or .xls)
2. Check filename contains date (YYYYMMDD format recommended)
3. Click "Reload Data" button
4. Check Google Drive folder directly

### Problem: Upload fails
**Solution:**
1. Check file size (must be under 50MB)
2. Check file format (.xlsx or .xls)
3. Verify folder permissions
4. Check Streamlit Cloud logs for errors

---

## 🎯 Daily Usage Workflow

1. **Morning:**
   - Prepare your Excel file
   - Open the dashboard
   - Upload the file via sidebar
   - Dashboard automatically shows new data

2. **During the Day:**
   - View dashboard anytime
   - Upload additional files if needed
   - Data persists in Google Drive

3. **End of Day:**
   - All files safely stored in Google Drive
   - Dashboard accessible 24/7
   - Historical data preserved

---

## 📞 Need Help?

If you encounter issues:
1. Check Streamlit Cloud logs (Settings → Logs)
2. Verify secrets are set correctly
3. Check Google Drive folder permissions
4. Make sure service account email matches
5. Verify JSON credentials are correct

---

## 🎉 You're All Set!

Your dashboard now:
- ✅ Reads files from Google Drive
- ✅ Allows file uploads through the interface
- ✅ Stores files securely in the cloud
- ✅ Works on any device
- ✅ Persists data forever
- ✅ Supports multiple users

**Next Steps:**
1. Test the upload functionality
2. Verify files appear in Google Drive
3. Check dashboard shows the data
4. Start using it daily!

