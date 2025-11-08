# 🚀 Deployment Steps - Let's Deploy!

Follow these steps to deploy your FCR Dashboard to Streamlit Cloud:

## ✅ Pre-Deployment Checklist

- [x] Main file: `FCR_DASHBOARD.py` ✓
- [x] Configuration: `.streamlit/config.toml` ✓
- [x] Dependencies: `requirements.txt` ✓
- [x] Git ignore: `.gitignore` ✓

## Step 1: Initialize Git (if not done)

Open PowerShell in your project folder:

```powershell
cd "C:\Users\dell\Desktop\FCR_DASHBOARD"

# Check if git is initialized
git status
```

If you see "not a git repository", initialize it:

```powershell
git init
```

## Step 2: Create GitHub Repository

1. Go to [github.com](https://github.com)
2. Click the **"+"** icon → **"New repository"**
3. Repository name: `fcr-dashboard` (or your preferred name)
4. Description: "FCR Daily Dashboard - Monitor pendency trends"
5. Choose **Public** (required for free Streamlit Cloud)
6. **DO NOT** check "Initialize with README" (you already have one)
7. Click **"Create repository"**

## Step 3: Push Code to GitHub

In PowerShell, run these commands:

```powershell
# Make sure you're in the project folder
cd "C:\Users\dell\Desktop\FCR_DASHBOARD"

# Add all files
git add .

# Commit changes
git commit -m "Initial commit - FCR Dashboard ready for deployment"

# Add your GitHub repository (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/fcr-dashboard.git

# Push to GitHub
git branch -M main
git push -u origin main
```

**Note**: You'll be prompted for your GitHub username and password (or token).

## Step 4: Deploy on Streamlit Cloud

1. **Go to Streamlit Cloud**: [share.streamlit.io](https://share.streamlit.io)

2. **Sign in** with your GitHub account

3. **Click "New app"** button

4. **Fill in the deployment form**:
   - **Repository**: Select `fcr-dashboard` (or your repo name)
   - **Branch**: `main`
   - **Main file path**: `FCR_DASHBOARD.py`
   - **App URL**: Choose a unique name (e.g., `fcr-dashboard`)

5. **Click "Deploy!"**

6. **Wait 2-3 minutes** for deployment

7. **Your app will be live!** 🎉

## Step 5: Upload Data Files

After deployment, you have two options:

### Option A: Add Files to GitHub Repository

1. Add Excel files to the `data/` folder
2. Commit and push:
   ```powershell
   git add data/
   git commit -m "Add data files"
   git push
   ```
3. Streamlit Cloud will automatically redeploy

### Option B: Use File Upload (if available)

- If you have the upload version, users can upload files through the web interface

## Step 6: Test Your Deployment

1. Visit your app URL: `https://YOUR-APP-NAME.streamlit.app`
2. Check if the dashboard loads
3. Verify data is displayed correctly
4. Test filters and features

## Troubleshooting

### "Repository not found"
- Make sure repository is **public** (required for free tier)
- Or verify the repository name is correct

### "Module not found"
- Check `requirements.txt` has all dependencies
- Verify version numbers are specified

### "No data available"
- Ensure Excel files are in the `data/` folder
- Check file naming format (should contain YYYYMMDD date)
- Verify files are committed to GitHub

### App won't start
- Check logs in Streamlit Cloud dashboard
- Look for error messages
- Verify `FCR_DASHBOARD.py` is the correct filename

## Quick Commands Reference

```powershell
# Navigate to project
cd "C:\Users\dell\Desktop\FCR_DASHBOARD"

# Check git status
git status

# Add all files
git add .

# Commit
git commit -m "Your commit message"

# Push to GitHub
git push

# Test locally
streamlit run FCR_DASHBOARD.py
```

## Next Steps After Deployment

1. ✅ Share the app URL with your team
2. ✅ Set up daily data uploads
3. ✅ Monitor app performance
4. ✅ Set up alerts (if needed)
5. ✅ Document usage for your team

## Support Resources

- **Streamlit Cloud Docs**: [docs.streamlit.io/streamlit-cloud](https://docs.streamlit.io/streamlit-cloud)
- **Deployment Guide**: See `STREAMLIT_DEPLOYMENT.md`
- **Checklist**: See `DEPLOYMENT_CHECKLIST.md`

---

**Ready? Let's deploy! 🚀**

