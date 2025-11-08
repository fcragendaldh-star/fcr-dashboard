# Enhanced FCR Dashboard with File Upload Capability
"""
Streamlit FCR Dashboard with File Upload
This version supports uploading Excel files directly through the web interface,
making it ideal for deployment on cloud platforms.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import re
from datetime import timedelta
import time
import logging
import os
import shutil
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="FCR Daily Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "FCR Dashboard - Monitor pendency trends and performance metrics"
    }
)

# ---------- CONFIG ----------
# Use persistent data folder (works in deployed environments)
DATA_FOLDER = Path("data")  # Local data folder
UPLOAD_FOLDER = Path("uploads")  # Folder for uploaded files
FILENAME_DATE_RE = re.compile(r'(\d{4}\d{2}\d{2})')  # matches YYYYMMDD
DATE_FORMAT = "%Y%m%d"

# Create folders if they don't exist
DATA_FOLDER.mkdir(exist_ok=True)
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Initialize session state
if "threshold_alert" not in st.session_state:
    st.session_state.threshold_alert = 50
if "data_folder" not in st.session_state:
    st.session_state.data_folder = str(DATA_FOLDER)
if "last_refresh_time" not in st.session_state:
    st.session_state.last_refresh_time = None
if "last_file_hash" not in st.session_state:
    st.session_state.last_file_hash = None
if "pending_file_update" not in st.session_state:
    st.session_state.pending_file_update = False
if "refresh_requested" not in st.session_state:
    st.session_state.refresh_requested = False
if "files_uploaded" not in st.session_state:
    st.session_state.files_uploaded = []

THRESHOLD_ALERT = st.session_state.threshold_alert

# ---------- FILE UPLOAD FUNCTIONS ----------

def save_uploaded_file(uploaded_file, destination_folder: Path):
    """Save uploaded file to destination folder"""
    try:
        # Create destination folder if it doesn't exist
        destination_folder.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = destination_folder / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        logger.info(f"File saved: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        return None

def validate_excel_file(file) -> tuple[bool, str]:
    """Validate uploaded Excel file"""
    try:
        # Check file extension
        if not file.name.endswith(('.xlsx', '.xls')):
            return False, "File must be an Excel file (.xlsx or .xls)"
        
        # Check file size (limit to 50MB)
        if file.size > 50 * 1024 * 1024:
            return False, "File size must be less than 50MB"
        
        # Try to read the file
        try:
            df = pd.read_excel(file, engine="openpyxl", nrows=1)
            if df.empty:
                return False, "File appears to be empty"
            
            # Check for required columns
            required_cols = ["Sub Division", "Officer"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                # Try case-insensitive match
                df_cols_lower = {c.lower().strip(): c for c in df.columns}
                missing_cols = [col for col in required_cols if col.lower() not in df_cols_lower]
                if missing_cols:
                    return False, f"File missing required columns: {', '.join(missing_cols)}"
        
        except Exception as e:
            return False, f"Error reading file: {str(e)}"
        
        return True, "File is valid"
    except Exception as e:
        return False, f"Error validating file: {str(e)}"

# ---------- HELPERS ----------

def calculate_change(current, previous):
    """Calculate percentage change between two values"""
    if previous == 0:
        return 0 if current == 0 else 100
    return ((current - previous) / previous) * 100

def get_trend_icon(change):
    """Get trend indicator icon"""
    if change > 0:
        return "📈"
    elif change < 0:
        return "📉"
    else:
        return "➡️"

def format_number(num):
    """Format number with commas"""
    try:
        return f"{int(num):,}"
    except (ValueError, TypeError):
        return "0"

def validate_dataframe(df: pd.DataFrame, filename: str):
    """Validate that dataframe has required structure"""
    if df.empty:
        return False, "File is empty"
    
    required_cols = ["Sub Division", "Officer"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return False, f"Missing required columns: {', '.join(missing_cols)}"
    
    return True, "OK"

# Core function to load and process Excel files (same as original)
def _load_all_files_core(folder_path: str) -> pd.DataFrame:
    """Core function to load all Excel files from the folder and process them."""
    folder = Path(folder_path)
    if not folder.exists():
        logger.warning(f"Data folder does not exist: {folder}")
        return pd.DataFrame()
    
    files = sorted(folder.glob("*.xlsx"))
    if not files:
        logger.info(f"No Excel files found in {folder}")
        return pd.DataFrame()
    
    rows = []
    failed_files = []
    
    for f in files:
        if f.name.startswith("~$"):
            continue
        
        try:
            try:
                df = pd.read_excel(f, engine="openpyxl")
            except Exception as e:
                logger.warning(f"Failed to read {f.name} with default sheet, trying first sheet: {e}")
                df = pd.read_excel(f, sheet_name=0, engine="openpyxl")
            
            if df.empty:
                logger.warning(f"File {f.name} is empty, skipping")
                failed_files.append((f.name, "Empty file"))
                continue
            
            df_cols = {c.lower().strip(): c for c in df.columns}
            
            if "total" not in df_cols:
                match = [c for c in df.columns if "total" in str(c).lower()]
                if match:
                    df.rename(columns={match[0]: "Total"}, inplace=True)
            
            if "sub division" not in df_cols:
                match = [c for c in df.columns if "sub" in str(c).lower() and "division" in str(c).lower()]
                if match:
                    df.rename(columns={match[0]: "Sub Division"}, inplace=True)
            
            is_valid, error_msg = validate_dataframe(df, f.name)
            if not is_valid:
                logger.warning(f"Validation failed for {f.name}: {error_msg}")
                failed_files.append((f.name, error_msg))
                continue
            
            m = FILENAME_DATE_RE.search(f.name)
            file_date = pd.to_datetime(m.group(1), format=DATE_FORMAT) if m else pd.NaT
            if pd.isna(file_date):
                logger.warning(f"Could not parse date from filename: {f.name}")
            
            df["__source_file"] = f.name
            df["__date"] = file_date
            rows.append(df)
            
        except Exception as e:
            logger.error(f"Error processing file {f.name}: {str(e)}")
            failed_files.append((f.name, str(e)))
            continue
    
    if not rows:
        if failed_files:
            logger.error(f"All files failed to load. Failed: {failed_files}")
        return pd.DataFrame()
    
    try:
        combined = pd.concat(rows, ignore_index=True, sort=False)
    except Exception as e:
        logger.error(f"Error concatenating dataframes: {str(e)}")
        return pd.DataFrame()
    
    if "Total" not in combined.columns and "TOTAL" in combined.columns:
        combined.rename(columns={"TOTAL": "Total"}, inplace=True)
    
    pendency_columns = [
        "Uncontested Pendency", "Income Certificate", "Copying Service",
        "Inspection Records", "Overdue Mortgage", "Overdue Court Orders",
        "Overdue Fardbadars"
    ]
    
    for col in pendency_columns:
        if col in combined.columns:
            combined[col] = pd.to_numeric(combined[col], errors="coerce").fillna(0).astype(int)
    
    if "Total" not in combined.columns:
        available_pendency_cols = [col for col in pendency_columns if col in combined.columns]
        if available_pendency_cols:
            combined["Total"] = combined[available_pendency_cols].sum(axis=1)
        else:
            combined["Total"] = 0
    else:
        combined["Total"] = pd.to_numeric(combined["Total"], errors="coerce").fillna(0).astype(int)
    
    if "Sub Division" not in combined.columns and "SubDivision" in combined.columns:
        combined.rename(columns={"SubDivision": "Sub Division"}, inplace=True)
    
    if "Rank" in combined.columns:
        combined["Rank"] = pd.to_numeric(combined["Rank"], errors="coerce")
    
    for col in ["Officer", "Sub Division"]:
        if col not in combined.columns:
            combined[col] = "Unknown"
    
    if failed_files:
        logger.warning(f"Some files failed to load: {failed_files}")
    
    return combined

@st.cache_data(ttl=300, show_spinner="Loading data files...")
def load_all_files(folder_path: str, cache_version: str = "v1") -> pd.DataFrame:
    """Load all Excel files from the folder."""
    return _load_all_files_core(folder_path)

def _load_all_files_uncached(folder_path: str) -> pd.DataFrame:
    """Load files without caching - used for refresh"""
    return _load_all_files_core(folder_path)

# ---------- UI ----------
# Include all the CSS and styling from the original file
# (Copy the entire CSS section from FCR_DASHBOARD.py here)
# For brevity, I'll include a simplified version - you should copy the full CSS

st.markdown("""
<style>
    /* Include all CSS from original FCR_DASHBOARD.py */
    /* Main container styling */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
        max-width: 1400px;
    }
    /* Add all other styles from original */
</style>
""", unsafe_allow_html=True)

# Title
st.markdown("""
<div class="title-header" style="background-color: #f8f9fa; padding: 1rem 1.5rem; margin-bottom: 1.5rem; border-bottom: 2px solid #003366;">
    <h1 style="color: #003366; margin: 0; padding: 0; border: none; font-size: 1.75rem; font-weight: 600;">FCR Daily Dashboard</h1>
    <p style="color: #666; font-size: 0.95rem; margin-top: 0.25rem; margin-bottom: 0; font-weight: 400;">
        Monitor pendency trends and performance metrics across sub-divisions and officers
    </p>
</div>
""", unsafe_allow_html=True)

# ---------- FILE UPLOAD SECTION ----------
st.sidebar.header("📤 Upload Excel Files")

uploaded_files = st.sidebar.file_uploader(
    "Upload Excel files",
    type=['xlsx', 'xls'],
    accept_multiple_files=True,
    help="Upload one or more Excel files. Files should contain date in filename (YYYYMMDD format)."
)

if uploaded_files:
    for uploaded_file in uploaded_files:
        # Validate file
        is_valid, message = validate_excel_file(uploaded_file)
        
        if is_valid:
            # Save file to data folder
            file_path = save_uploaded_file(uploaded_file, DATA_FOLDER)
            if file_path:
                st.sidebar.success(f"✅ {uploaded_file.name} uploaded successfully!")
                st.session_state.files_uploaded.append(uploaded_file.name)
                # Clear cache to force reload
                load_all_files.clear()
                st.session_state.refresh_requested = True
            else:
                st.sidebar.error(f"❌ Failed to save {uploaded_file.name}")
        else:
            st.sidebar.error(f"❌ {uploaded_file.name}: {message}")

# Show uploaded files
if st.session_state.files_uploaded:
    with st.sidebar.expander("📋 Uploaded Files", expanded=False):
        for file in st.session_state.files_uploaded:
            st.write(f"• {file}")

# File management
st.sidebar.divider()
st.sidebar.header("🗂️ File Management")

# List existing files
if DATA_FOLDER.exists():
    existing_files = sorted([f.name for f in DATA_FOLDER.glob("*.xlsx") if not f.name.startswith("~$")])
    if existing_files:
        st.sidebar.write(f"**{len(existing_files)} file(s) in data folder:**")
        for file in existing_files[-5:]:  # Show last 5
            st.sidebar.write(f"• {file}")
        if len(existing_files) > 5:
            st.sidebar.write(f"... and {len(existing_files) - 5} more")

# Clear all files button (with confirmation)
if st.sidebar.button("🗑️ Clear All Files", help="Remove all uploaded files"):
    if st.sidebar.checkbox("I'm sure I want to delete all files"):
        try:
            for file in DATA_FOLDER.glob("*.xlsx"):
                if not file.name.startswith("~$"):
                    file.unlink()
            st.session_state.files_uploaded = []
            load_all_files.clear()
            st.sidebar.success("All files cleared!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error clearing files: {e}")

# Continue with the rest of the original dashboard code...
# (Copy the rest of FCR_DASHBOARD.py starting from the data loading section)

# Use session state data folder
data_folder = st.session_state.data_folder
DATA_FOLDER = Path(data_folder)

# Settings and rest of dashboard...
# (Include all the remaining code from FCR_DASHBOARD.py)

st.info("""
**Note:** This is a template for the enhanced version with file upload.
To complete the implementation, copy the remaining code from FCR_DASHBOARD.py
starting from the "Settings row" section onwards.
""")

