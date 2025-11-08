# Deployment Checklist

Use this checklist to ensure your FCR Dashboard is ready for deployment.

## Pre-Deployment

- [ ] **Code is complete and tested locally**
  - [ ] Dashboard runs without errors
  - [ ] All features work as expected
  - [ ] Data loads correctly

- [ ] **Files are properly organized**
  - [ ] Main file: `FCR_DASHBOARD.py`
  - [ ] `requirements.txt` is present and up-to-date
  - [ ] `.streamlit/config.toml` is configured
  - [ ] `.gitignore` excludes unnecessary files

- [ ] **Dependencies are correct**
  - [ ] All required packages are in `requirements.txt`
  - [ ] Version numbers are specified
  - [ ] No unnecessary dependencies

- [ ] **Data folder is configured**
  - [ ] Data folder path is configurable (via environment variable)
  - [ ] Folder will be created automatically if missing
  - [ ] File upload is working (if using upload feature)

## GitHub Repository

- [ ] **Repository is set up**
  - [ ] Code is pushed to GitHub
  - [ ] Repository is public (for Streamlit Cloud free tier) or private (for paid plans)
  - [ ] README.md is updated with deployment instructions
  - [ ] .gitignore is properly configured

- [ ] **Files are committed**
  - [ ] All necessary files are committed
  - [ ] No sensitive data is committed (use .gitignore)
  - [ ] No large files are committed (use Git LFS if needed)

## Streamlit Cloud Deployment

- [ ] **Account is set up**
  - [ ] Streamlit Cloud account created
  - [ ] GitHub account connected
  - [ ] Repository is accessible

- [ ] **App is configured**
  - [ ] Repository selected
  - [ ] Branch selected (usually `main`)
  - [ ] Main file path is correct: `FCR_DASHBOARD.py`
  - [ ] App URL is chosen

- [ ] **Environment variables (if needed)**
  - [ ] `DATA_FOLDER` is set (if using custom path)
  - [ ] Other environment variables are configured

## Post-Deployment

- [ ] **App is accessible**
  - [ ] App URL is working
  - [ ] Dashboard loads correctly
  - [ ] No errors in logs

- [ ] **Data is loading**
  - [ ] Files are accessible
  - [ ] Data loads correctly
  - [ ] Filters work properly

- [ ] **Features are working**
  - [ ] Charts display correctly
  - [ ] Filters work
  - [ ] Download functionality works
  - [ ] File upload works (if enabled)

- [ ] **Performance is acceptable**
  - [ ] Page loads quickly
  - [ ] Charts render smoothly
  - [ ] No timeout errors

## Testing

- [ ] **Functional testing**
  - [ ] Test with sample data
  - [ ] Test with empty data folder
  - [ ] Test with invalid data
  - [ ] Test all filters
  - [ ] Test download functionality

- [ ] **Edge cases**
  - [ ] Handle missing files gracefully
  - [ ] Handle invalid file formats
  - [ ] Handle empty data
  - [ ] Handle large datasets

## Security

- [ ] **Authentication (if needed)**
  - [ ] Password protection is configured
  - [ ] OAuth is set up (if using)
  - [ ] Access control is working

- [ ] **Data security**
  - [ ] Sensitive data is not exposed
  - [ ] File uploads are validated
  - [ ] HTTPS is enabled (automatic on Streamlit Cloud)

## Monitoring

- [ ] **Logs are accessible**
  - [ ] Can view application logs
  - [ ] Can view error logs
  - [ ] Logging is configured

- [ ] **Monitoring is set up**
  - [ ] Uptime monitoring (optional)
  - [ ] Error tracking (optional)
  - [ ] Performance monitoring (optional)

## Documentation

- [ ] **Documentation is complete**
  - [ ] README.md is updated
  - [ ] Deployment guide is available
  - [ ] User guide is available (if needed)

## Notes

- **File naming**: File is now named `FCR_DASHBOARD.py` (no spaces) for better compatibility
- **Data persistence**: On Streamlit Cloud free tier, files may not persist. Consider using cloud storage for production
- **Performance**: Monitor app performance and optimize if needed
- **Updates**: Plan for regular updates and maintenance

## Quick Deployment Commands

```bash
# 1. Check git status
git status

# 2. Add all files
git add .

# 3. Commit changes
git commit -m "Ready for deployment"

# 4. Push to GitHub
git push origin main

# 5. Deploy on Streamlit Cloud
# Go to share.streamlit.io and follow the deployment steps
```

## Troubleshooting

If deployment fails:
1. Check logs for errors
2. Verify all files are committed
3. Check requirements.txt for issues
4. Verify file paths are correct
5. Check environment variables
6. Review Streamlit Cloud documentation

