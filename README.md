# FCR Dashboard

A Streamlit-based dashboard for monitoring FCR (First Class Revenue) pendency trends and performance metrics across sub-divisions and officers.

## Features

- **Executive Dashboard**: High-level metrics, trends, and alerts
- **Summary View**: Detailed breakdowns and comprehensive data tables
- **Interactive Filters**: Filter by date range, sub-division, tehsil, and officer
- **Visual Analytics**: 
  - Trend charts
  - Bar charts by sub-division
  - Heatmaps showing pendency hotspots
  - Stacked bar charts for pendency type breakdowns
- **Data Export**: Download filtered data as CSV
- **Alert System**: Configurable threshold-based alerts for high pendency areas
- **Mobile Responsive**: Fully optimized for mobile devices with touch-friendly controls and responsive layouts
- **File Upload**: Upload Excel files directly through the web interface (in enhanced version)

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Ensure your Excel files are in the `data/` folder with filenames containing dates in `YYYYMMDD` format (e.g., `FCR_Agenda_20251104.xlsx`)

## Usage

### Local Development

Run the dashboard:
```bash
streamlit run FCR_DASHBOARD.py
```

### With File Upload (Enhanced Version)

Run the enhanced version with file upload capability:
```bash
streamlit run FCR_DASHBOARD_WITH_UPLOAD.py
```

## Data Format

Excel files should contain the following columns:
- `Sub Division`
- `Officer`
- `Tehsil/Sub Tehsil` (optional)
- `Uncontested Pendency`
- `Income Certificate`
- `Copying Service`
- `Inspection Records`
- `Overdue Mortgage`
- `Overdue Court Orders`
- `Overdue Fardbadars`
- `Total` (or will be calculated automatically)

## Deployment

The dashboard is now **ready for deployment** to Streamlit Cloud and other platforms!

### Quick Start - Streamlit Cloud (Free)

1. **Push code to GitHub:**
   ```bash
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

2. **Deploy on Streamlit Cloud:**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Click "New app"
   - Select your repository
   - Main file path: `FCR_DASHBOARD.py`
   - Click "Deploy!"

3. **Your app will be live in minutes!**

### Deployment Documentation

- **[STREAMLIT_DEPLOYMENT.md](STREAMLIT_DEPLOYMENT.md)** - Step-by-step Streamlit Cloud deployment guide
- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Detailed deployment options and strategies
- **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Pre-deployment checklist
- **[QUICK_DEPLOY.md](QUICK_DEPLOY.md)** - Quick deployment guide for multiple platforms

### Deployment Features

✅ **Automatically creates data folder** if it doesn't exist  
✅ **Environment variable support** for data folder path  
✅ **Deployment-ready configuration** (`.streamlit/config.toml`)  
✅ **Optimized dependencies** (`requirements.txt`)  
✅ **Error handling** for deployment environments  
✅ **Cross-platform compatibility**

### Other Deployment Options

1. **Railway** (~$5-10/month):
   - Persistent storage
   - Easy deployment
   - Good for production

2. **Render.com** (Free tier available):
   - Easy deployment from GitHub
   - Persistent disk storage (paid plans)

3. **Self-Hosted VPS**:
   - Deploy on VPS (DigitalOcean, Linode, etc.)
   - Full control
   - ~$5-10/month

## Configuration

- **Alert Threshold**: Set in the dashboard UI (default: 50)
- **Data Folder**: Configured via environment variable `DATA_FOLDER` (default: `data/`)
- **Port**: Configured in `.streamlit/config.toml` (default: 8501)

## Developer

Developed by **Shivam Gulati** - Land Revenue Fellow

