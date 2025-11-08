# Enable Google Drive Integration in Streamlit Cloud

Your app is currently using the basic version that reads from local files. To use Google Drive, you need to:

## Step 1: Update Main File in Streamlit Cloud

1. **Go to your Streamlit Cloud dashboard**: [share.streamlit.io](https://share.streamlit.io)
2. **Click on your app** (`fcragenda`)
3. **Click "⚙️ Settings"** (top right)
4. **Find "Main file path"**
5. **Change it from**: `FCR DASHBOARD.py`
6. **Change it to**: `FCR_DASHBOARD_GOOGLE_DRIVE.py`
7. **Click "Save"**
8. **The app will automatically redeploy**

## Step 2: Add Google Drive Dependencies

Make sure `requirements.txt` includes Google API packages. Let me check and update it if needed.

## Step 3: Configure Google Drive Secrets

You need to add these secrets in Streamlit Cloud:

1. **Go to your app settings** → **"Secrets"** tab
2. **Add these two secrets**:

### Secret 1: Google Drive Folder ID
```
GOOGLE_DRIVE_FOLDER_ID = "YOUR_GOOGLE_DRIVE_FOLDER_ID_HERE"
```
Replace `YOUR_GOOGLE_DRIVE_FOLDER_ID_HERE` with your actual Google Drive folder ID.

**How to find your folder ID:**
- Open your Google Drive folder
- Look at the URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
- Copy the `FOLDER_ID_HERE` part

### Secret 2: Google Service Account Credentials
```
GOOGLE_APPLICATION_CREDENTIALS_JSON = '{"type":"service_account","project_id":"your-project-id",...}'
```
Paste your complete service account JSON credentials here.

**How to get credentials:**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a service account (if you haven't)
3. Download the JSON key file
4. Copy the entire JSON content
5. Paste it as the value for `GOOGLE_APPLICATION_CREDENTIALS_JSON`

## Step 4: Share Google Drive Folder

Make sure your Google Drive folder is shared with the service account email:
- **Email**: `your-service-account@your-project.iam.gserviceaccount.com`
- **Permission**: Editor

## Step 5: Verify Deployment

After updating:
1. Wait for the app to redeploy (1-2 minutes)
2. Check the logs for any errors
3. The dashboard should now load files from Google Drive
4. You should see a file upload button in the sidebar

## Troubleshooting

### "No data available"
- Check that files are in the Google Drive folder
- Verify folder ID is correct
- Check that service account has access to the folder

### "Google Drive not configured"
- Verify secrets are added correctly in Streamlit Cloud
- Check that JSON credentials are valid
- Make sure folder ID is correct

### "Module not found"
- Verify `requirements.txt` includes Google API packages
- Check app logs for missing dependencies

---

**After completing these steps, your dashboard will read files from Google Drive!**

