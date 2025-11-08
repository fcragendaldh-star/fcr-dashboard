# 📦 GitHub Repository Setup

Your code is committed locally! Now let's push it to GitHub.

## Step 1: Create GitHub Repository

1. **Go to GitHub**: [github.com](https://github.com)
2. **Sign in** to your account
3. **Click the "+" icon** (top right) → **"New repository"**
4. **Repository name**: `fcr-dashboard` (or your preferred name)
5. **Description**: "FCR Daily Dashboard - Monitor pendency trends and performance metrics"
6. **Visibility**: Choose **Public** (required for free Streamlit Cloud)
7. **Important**: **DO NOT** check these boxes:
   - ❌ Initialize with README
   - ❌ Add .gitignore
   - ❌ Choose a license
   
   (You already have these files!)
8. **Click "Create repository"**

## Step 2: Connect Your Local Repository

After creating the repository, GitHub will show you commands. Use these:

```powershell
# Make sure you're in the project folder
cd "C:\Users\dell\Desktop\FCR_DASHBOARD"

# Add your GitHub repository as remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/fcr-dashboard.git

# Rename branch to main (if needed)
git branch -M main

# Push your code to GitHub
git push -u origin main
```

## Step 3: Verify Upload

1. Go to your repository on GitHub
2. You should see all your files:
   - `FCR_DASHBOARD.py`
   - `requirements.txt`
   - `.streamlit/config.toml`
   - `README.md`
   - etc.

## Step 4: Deploy on Streamlit Cloud

Once your code is on GitHub:

1. **Go to Streamlit Cloud**: [share.streamlit.io](https://share.streamlit.io)
2. **Sign in** with your GitHub account
3. **Click "New app"**
4. **Fill in**:
   - Repository: `fcr-dashboard` (or your repo name)
   - Branch: `main`
   - Main file path: `FCR_DASHBOARD.py`
   - App URL: Choose a unique name
5. **Click "Deploy!"**
6. **Wait 2-3 minutes**
7. **Your app is live!** 🎉

## Quick Reference

**Your repository URL will be:**
```
https://github.com/YOUR_USERNAME/fcr-dashboard
```

**Your Streamlit app URL will be:**
```
https://fcr-dashboard.streamlit.app
```
(Or whatever name you chose)

## Troubleshooting

### "Repository already exists"
- The remote is already added. Use: `git remote set-url origin https://github.com/YOUR_USERNAME/fcr-dashboard.git`

### "Authentication failed"
- Use a Personal Access Token instead of password
- Generate token: GitHub → Settings → Developer settings → Personal access tokens → Generate new token
- Use token as password when pushing

### "Branch name mismatch"
- If GitHub uses `main` but you have `master`: `git branch -M main`
- Then push: `git push -u origin main`

---

**Next**: After pushing to GitHub, deploy on Streamlit Cloud! 🚀

