# app.py
"""
Streamlit FCR Dashboard with Google Drive Integration
Reads cleaned daily Excel files from Google Drive or local folder and shows:
- Total pendency by Sub Division (bar)
- Trend over time (line)
- Officer-level table with ranks
- Top/Bottom performers and alerts
- CSV export and download
- File upload to Google Drive
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
from io import BytesIO

# Try to import Google Drive storage
try:
    from google_drive_storage import GoogleDriveStorage
    GOOGLE_DRIVE_AVAILABLE = True
except Exception as e:
    GOOGLE_DRIVE_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"Google Drive not available: {e}")

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
DATA_FOLDER = Path("data")  # Local fallback folder
FILENAME_DATE_RE = re.compile(r'(\d{4}\d{2}\d{2})')  # matches YYYYMMDD
DATE_FORMAT = "%Y%m%d"

# Initialize Google Drive storage if configured
storage = None
use_google_drive = False

if GOOGLE_DRIVE_AVAILABLE:
    try:
        storage = GoogleDriveStorage()
        use_google_drive = True
        logger.info("Google Drive storage initialized successfully")
    except Exception as e:
        logger.warning(f"Google Drive not configured, using local storage: {e}")
        use_google_drive = False
        DATA_FOLDER.mkdir(exist_ok=True)
else:
    DATA_FOLDER.mkdir(exist_ok=True)

# Initialize session state for settings persistence
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
if "upload_success" not in st.session_state:
    st.session_state.upload_success = None

THRESHOLD_ALERT = st.session_state.threshold_alert

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
            
            # Check for required columns (case-insensitive)
            required_cols = ["Sub Division", "Officer"]
            df_cols_lower = {c.lower().strip(): c for c in df.columns}
            missing_cols = [col for col in required_cols if col.lower() not in df_cols_lower]
            if missing_cols:
                return False, f"File missing required columns: {', '.join(missing_cols)}"
        
        except Exception as e:
            return False, f"Error reading file: {str(e)}"
        
        return True, "File is valid"
    except Exception as e:
        return False, f"Error validating file: {str(e)}"

# Core function to load and process Excel files from Google Drive or local
def _load_all_files_core(folder_path: str = None) -> pd.DataFrame:
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
        # Skip temporary Excel files (lock files created by Excel when file is open)
        if f.name.startswith("~$"):
            continue
        
        try:
            # Try to read Excel file
            try:
                df = pd.read_excel(f, engine="openpyxl")
            except Exception as e:
                logger.warning(f"Failed to read {f.name} with default sheet, trying first sheet: {e}")
                df = pd.read_excel(f, sheet_name=0, engine="openpyxl")
            
            if df.empty:
                logger.warning(f"File {f.name} is empty, skipping")
                failed_files.append((f.name, "Empty file"))
                continue
            
            # Normalize column names
            df_cols = {c.lower().strip(): c for c in df.columns}
            
            # Try to find and rename Total column
            if "total" not in df_cols:
                match = [c for c in df.columns if "total" in str(c).lower()]
                if match:
                    df.rename(columns={match[0]: "Total"}, inplace=True)
            
            # Try to find and rename Sub Division column
            if "sub division" not in df_cols:
                match = [c for c in df.columns if "sub" in str(c).lower() and "division" in str(c).lower()]
                if match:
                    df.rename(columns={match[0]: "Sub Division"}, inplace=True)
            
            # Validate dataframe
            is_valid, error_msg = validate_dataframe(df, f.name)
            if not is_valid:
                logger.warning(f"Validation failed for {f.name}: {error_msg}")
                failed_files.append((f.name, error_msg))
                continue
            
            # Parse date from filename
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
    
    # Standardize column names
    if "Total" not in combined.columns and "TOTAL" in combined.columns:
        combined.rename(columns={"TOTAL": "Total"}, inplace=True)
    
    # Define pendency columns
    pendency_columns = [
        "Uncontested Pendency", "Income Certificate", "Copying Service",
        "Inspection Records", "Overdue Mortgage", "Overdue Court Orders",
        "Overdue Fardbadars"
    ]
    
    # Convert all pendency columns to numeric
    for col in pendency_columns:
        if col in combined.columns:
            combined[col] = pd.to_numeric(combined[col], errors="coerce").fillna(0).astype(int)
    
    # Calculate Total if it doesn't exist (sum of all pendency columns)
    if "Total" not in combined.columns:
        available_pendency_cols = [col for col in pendency_columns if col in combined.columns]
        if available_pendency_cols:
            combined["Total"] = combined[available_pendency_cols].sum(axis=1)
        else:
            combined["Total"] = 0
    else:
        # Convert Total to numeric if it exists
        combined["Total"] = pd.to_numeric(combined["Total"], errors="coerce").fillna(0).astype(int)
    
    # Ensure Sub Division column
    if "Sub Division" not in combined.columns and "SubDivision" in combined.columns:
        combined.rename(columns={"SubDivision": "Sub Division"}, inplace=True)
    
    # Standardize Rank (optional - only if exists)
    if "Rank" in combined.columns:
        combined["Rank"] = pd.to_numeric(combined["Rank"], errors="coerce")
    
    # Fill missing useful columns
    for col in ["Officer", "Sub Division"]:
        if col not in combined.columns:
            combined[col] = "Unknown"
    
    if failed_files:
        logger.warning(f"Some files failed to load: {failed_files}")
    
    return combined

# Non-cached version for when we need fresh data
def _load_all_files_uncached(folder_path: str = None) -> pd.DataFrame:
    """Load files without caching - used for refresh"""
    return _load_all_files_core(folder_path)

# Cached version for normal operation
@st.cache_data(ttl=300, show_spinner="Loading data files...")
def load_all_files(folder_path: str = None, cache_version: str = "v1") -> pd.DataFrame:
    """
    Load all Excel files from Google Drive or local folder.
    cache_version is used to force cache refresh when files change.
    """
    return _load_all_files_core(folder_path)

# ---------- UI ----------
# Official Professional Styling with Mobile Responsiveness
st.markdown("""
<style>
    /* Mobile-first viewport settings */
    @media screen and (max-width: 768px) {
        /* Main container styling - mobile */
        .main .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 100%;
        }
        
        /* Official title styling - mobile */
        h1 {
            font-size: 1.4rem !important;
            margin-bottom: 0.3rem;
            padding-bottom: 0.3rem;
        }
        
        /* Section headers - mobile */
        h2 {
            font-size: 1.1rem !important;
            margin-top: 1rem;
            margin-bottom: 0.5rem;
            padding: 0.3rem 0;
        }
        
        h3 {
            font-size: 1rem !important;
            margin-top: 0.8rem;
            margin-bottom: 0.4rem;
        }
        
        /* Metric cards - mobile */
        [data-testid="stMetricValue"] {
            font-size: 1.5rem !important;
        }
        
        [data-testid="stMetricDelta"] {
            font-size: 0.85rem !important;
        }
        
        [data-testid="stMetricLabel"] {
            font-size: 0.8rem !important;
        }
        
        /* Sidebar - mobile */
        [data-testid="stSidebar"] {
            min-width: 200px;
        }
        
        /* Buttons - mobile - larger touch targets */
        .stButton > button {
            min-height: 44px;
            font-size: 0.95rem;
            padding: 0.6rem 1rem;
        }
        
        /* Tables - mobile - horizontal scroll */
        .dataframe {
            font-size: 0.85rem;
            display: block;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        
        /* Chart container - mobile */
        .js-plotly-plot {
            width: 100% !important;
            height: auto !important;
        }
        
        /* Selectboxes and inputs - mobile */
        .stSelectbox > div > div,
        .stNumberInput > div > div > input,
        .stDateInput > div > div > input {
            font-size: 16px !important; /* Prevents zoom on iOS */
            min-height: 44px;
        }
        
        /* Tabs - mobile */
        [data-baseweb="tab-list"] {
            flex-wrap: wrap;
        }
        
        [data-baseweb="tab"] {
            min-height: 44px;
            font-size: 0.9rem;
        }
        
        /* Footer text - mobile */
        .element-container {
            font-size: 0.8rem;
        }
        
        /* Column spacing - mobile */
        .row-widget.stHorizontal {
            flex-wrap: wrap;
        }
    }
    
    /* Tablet adjustments */
    @media screen and (min-width: 769px) and (max-width: 1024px) {
        .main .block-container {
            padding-left: 2rem;
            padding-right: 2rem;
            max-width: 100%;
        }
        
        h1 {
            font-size: 1.6rem;
        }
        
        [data-testid="stMetricValue"] {
            font-size: 1.75rem;
        }
    }
    
    /* Desktop styling */
    @media screen and (min-width: 1025px) {
        .main .block-container {
            padding-top: 1.5rem;
            padding-bottom: 1.5rem;
            max-width: 1400px;
        }
    }
    
    /* Main container styling - base */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
    }
    
    /* Official title styling - subtle */
    h1 {
        color: #003366;
        font-weight: 600;
        font-size: 1.75rem;
        margin-bottom: 0.5rem;
        padding-bottom: 0.5rem;
        letter-spacing: 0.3px;
        word-wrap: break-word;
    }
    
    /* Section headers - subtle and clean */
    h2 {
        color: #003366;
        font-weight: 600;
        font-size: 1.2rem;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
        padding: 0.5rem 0;
        border-bottom: 2px solid #e0e0e0;
        word-wrap: break-word;
    }
    
    h3 {
        color: #003366;
        font-weight: 600;
        font-size: 1.1rem;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
        word-wrap: break-word;
    }
    
    /* Metric cards - prominent and clear */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #003366;
    }
    
    [data-testid="stMetricDelta"] {
        font-size: 1rem;
        font-weight: 600;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        font-weight: 500;
        color: #666;
    }
    
    /* Professional info boxes */
    .stInfo {
        background-color: #f0f7ff;
        border-left: 4px solid #0066cc;
        border-radius: 2px;
        padding: 0.75rem;
        margin: 0.5rem 0;
    }
    
    .stSuccess {
        background-color: #f0fff4;
        border-left: 4px solid #28a745;
        border-radius: 2px;
        padding: 0.75rem;
        margin: 0.5rem 0;
    }
    
    .stWarning {
        background-color: #fffbf0;
        border-left: 4px solid #ff9800;
        border-radius: 2px;
        padding: 0.75rem;
        margin: 0.5rem 0;
    }
    
    .stError {
        background-color: #fff0f0;
        border-left: 4px solid #dc3545;
        border-radius: 2px;
        padding: 0.75rem;
        margin: 0.5rem 0;
    }
    
    /* Professional sidebar */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
    }
    
    /* Sidebar on mobile - ensure it's accessible */
    @media screen and (max-width: 768px) {
        [data-testid="stSidebar"][aria-expanded="true"] {
            min-width: 250px;
        }
    }
    
    /* Professional dividers */
    hr {
        border: none;
        height: 1px;
        background-color: #e0e0e0;
        margin: 1.5rem 0;
    }
    
    @media screen and (max-width: 768px) {
        hr {
            margin: 1rem 0;
        }
    }
    
    /* Professional button styling */
    .stButton > button {
        background-color: #003366;
        color: white;
        border: 1px solid #003366;
        border-radius: 4px;
        font-weight: 500;
        transition: background-color 0.2s ease;
        min-height: 38px;
        padding: 0.5rem 1rem;
    }
    
    .stButton > button:hover {
        background-color: #004488;
        border-color: #004488;
    }
    
    .stButton > button:active {
        transform: scale(0.98);
    }
    
    /* Professional table styling */
    .dataframe {
        border: 1px solid #e0e0e0;
        border-radius: 2px;
        width: 100%;
        overflow-x: auto;
    }
    
    /* Make tables scrollable on mobile */
    @media screen and (max-width: 768px) {
        div[data-testid="stDataFrame"] {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
    }
    
    /* Professional progress bar */
    .stProgress > div > div > div {
        background-color: #0066cc;
    }
    
    /* Chart container - clean and responsive */
    .js-plotly-plot {
        border: 1px solid #e0e0e0;
        border-radius: 2px;
        width: 100% !important;
        max-width: 100%;
    }
    
    /* Ensure plotly charts are responsive */
    .plotly {
        width: 100% !important;
        height: 100% !important;
    }
    
    /* Mobile-specific chart adjustments */
    @media screen and (max-width: 768px) {
        .plotly .modebar {
            display: none !important; /* Hide modebar on mobile for cleaner view */
        }
        
        /* Make legends horizontal on mobile for better readability */
        .js-plotly-plot .legend {
            position: relative !important;
        }
        
        /* Adjust chart heights for mobile */
        .js-plotly-plot {
            min-height: 250px !important;
        }
        
        /* Better margins for mobile charts */
        .plotly .plot-container {
            padding: 5px !important;
        }
    }
    
    /* Title header - responsive */
    .title-header {
        padding: 1rem 1.5rem;
        margin-bottom: 1.5rem;
    }
    
    @media screen and (max-width: 768px) {
        .title-header {
            padding: 0.75rem 1rem;
            margin-bottom: 1rem;
        }
        
        .title-header h1 {
            font-size: 1.4rem !important;
        }
        
        .title-header p {
            font-size: 0.85rem !important;
        }
    }
    
    /* Column layouts - ensure they stack on mobile */
    @media screen and (max-width: 768px) {
        /* Force single column layout for metrics on mobile */
        .element-container:has([data-testid="stMetric"]) {
            width: 100% !important;
            margin-bottom: 0.5rem;
        }
        
        /* Make Streamlit columns stack on mobile */
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
            margin-bottom: 1rem;
        }
        
        /* Ensure row containers wrap */
        .row-widget.stHorizontal {
            flex-direction: column !important;
        }
        
        /* Settings row - stack on mobile */
        div[data-testid="column"]:has(input),
        div[data-testid="column"]:has(button) {
            width: 100% !important;
        }
    }
    
    /* Improve touch targets for all interactive elements */
    button, 
    [role="button"],
    input[type="checkbox"],
    input[type="radio"],
    select,
    .stSelectbox label,
    .stNumberInput label,
    .stDateInput label {
        min-height: 44px;
        min-width: 44px;
    }
    
    /* Text inputs - prevent zoom on iOS */
    input[type="text"],
    input[type="number"],
    input[type="date"],
    select {
        font-size: 16px !important;
    }
    
    /* Improve readability on mobile */
    @media screen and (max-width: 768px) {
        p, li, span, div {
            font-size: 0.9rem;
            line-height: 1.6;
        }
        
        /* Captions */
        .stCaption {
            font-size: 0.75rem;
        }
    }
    
    /* Better spacing for mobile */
    @media screen and (max-width: 768px) {
        .element-container {
            margin-bottom: 0.75rem;
        }
    }
    
    /* Card-like elements - better mobile display */
    @media screen and (max-width: 768px) {
        div[style*="background"] {
            padding: 0.75rem !important;
            margin: 0.5rem 0 !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# Official Title - Responsive
st.markdown("""
<div class="title-header" style="background-color: #f8f9fa; padding: 1rem 1.5rem; margin-bottom: 1.5rem; border-bottom: 2px solid #003366;">
    <h1 style="color: #003366; margin: 0; padding: 0; border: none; font-size: 1.75rem; font-weight: 600;">FCR Daily Dashboard</h1>
    <p style="color: #666; font-size: 0.95rem; margin-top: 0.25rem; margin-bottom: 0; font-weight: 400;">
        Monitor pendency trends and performance metrics across sub-divisions and officers
    </p>
</div>
""", unsafe_allow_html=True)

# Use session state data folder (no user input needed)
data_folder = st.session_state.data_folder
DATA_FOLDER = Path(data_folder)

# Settings row - only show essential controls
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    threshold = st.number_input(
        "⚠️ Alert threshold (Total >)",
        value=int(st.session_state.threshold_alert),
        min_value=0,
        step=50,
        help="Sub-divisions with Total above this value will trigger alerts"
    )
    # Update session state
    st.session_state.threshold_alert = threshold
with col2:
    # Beautiful reload button with custom styling
    st.markdown("""
    <style>
    div[data-testid="stButton"] > button[kind="primary"][data-baseweb="button"] {
        background-color: #0066cc !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1.5rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 4px rgba(31, 119, 180, 0.3) !important;
        width: 100% !important;
    }
    div[data-testid="stButton"] > button[kind="primary"][data-baseweb="button"]:hover {
        background-color: #0066cc !important;
        box-shadow: 0 4px 8px rgba(31, 119, 180, 0.4) !important;
        transform: translateY(-1px) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    if st.button("🔄 Reload Data", type="primary", width='stretch', key="reload_button"):
        # Set flag in session state to persist across reruns
        st.session_state.refresh_requested = True
        st.rerun()
    
    refresh = st.session_state.get("refresh_requested", False)
with col3:
    # Hidden clear cache functionality - only triggered on refresh if needed
    pass

# Generate cache key based on files in folder/Google Drive to detect new files
if use_google_drive and storage:
    try:
        drive_files = storage.list_files()
        # Use file names and modification times for cache key
        file_info = [(f['name'], f.get('modifiedTime', '')) for f in drive_files]
        file_info_sorted = tuple(sorted(file_info))
        current_file_hash = str(hash(file_info_sorted))
        current_file_hash = f"{current_file_hash}_{len(file_info)}"
        files_changed = (st.session_state.last_file_hash is None or 
                         st.session_state.last_file_hash != current_file_hash)
    except:
        current_file_hash = None
        files_changed = False
elif DATA_FOLDER.exists():
    files_in_folder = sorted([f.name for f in DATA_FOLDER.glob("*.xlsx") if not f.name.startswith("~$")])
    # Use file names, modification times, and file sizes for cache key (more reliable detection)
    file_info = []
    for f in DATA_FOLDER.glob("*.xlsx"):
        if not f.name.startswith("~$"):
            try:
                stat = f.stat()
                file_info.append((f.name, stat.st_mtime, stat.st_size))
            except Exception as e:
                logger.warning(f"Could not get file stats for {f.name}: {e}")
                file_info.append((f.name, 0, 0))
    # Sort by filename for consistent hashing
    file_info_sorted = tuple(sorted(file_info))
    current_file_hash = str(hash(file_info_sorted))
    # Also include file count for better detection
    current_file_hash = f"{current_file_hash}_{len(file_info)}"
    
    # Check if files have changed since last load
    files_changed = (st.session_state.last_file_hash is None or 
                     st.session_state.last_file_hash != current_file_hash)
else:
    current_file_hash = None
    files_changed = False

# Initialize cache version in session state
if "cache_version" not in st.session_state:
    st.session_state.cache_version = "v1"

# Update session state for refresh tracking
if refresh:
    st.session_state.last_refresh_time = time.time()
    st.session_state.last_file_hash = current_file_hash if DATA_FOLDER.exists() else None
    st.session_state.pending_file_update = False
    st.session_state.force_uncached_load = True
elif files_changed:
    # Files changed - clear cache and update version
    load_all_files.clear()
    if "cache_version" in st.session_state:
        version_num = int(st.session_state.cache_version.replace("v", "")) if st.session_state.cache_version.replace("v", "").isdigit() else 0
        st.session_state.cache_version = f"v{version_num + 1}"
    else:
        st.session_state.cache_version = f"v{int(time.time())}"
    st.session_state.pending_file_update = True

# Load data - use uncached version if refresh was clicked
if refresh or st.session_state.get("force_uncached_load", False):
    # Clear cache first
    load_all_files.clear()
    # Use uncached version to get fresh data
    with st.spinner("Loading data (fresh reload)..."):
        folder_path = str(DATA_FOLDER) if not use_google_drive else None
        df_all = _load_all_files_uncached(folder_path)
    
    # Clear the refresh flag after loading
    st.session_state.refresh_requested = False
    st.session_state.force_uncached_load = False
    
    # Update cache version so cached version also updates
    if "cache_version" not in st.session_state:
        st.session_state.cache_version = "v1"
    try:
        version_num = int(st.session_state.cache_version.replace("v", "")) if st.session_state.cache_version.replace("v", "").isdigit() else 0
        st.session_state.cache_version = f"v{version_num + 1}"
    except:
        st.session_state.cache_version = f"v{int(time.time())}"
    
    st.success("✅ Data refreshed successfully!")
else:
    # Use cached version for normal operation
    with st.spinner("Loading data..."):
        folder_path = str(DATA_FOLDER) if not use_google_drive else None
        df_all = load_all_files(folder_path, cache_version=st.session_state.cache_version)


# Update file hash after successful load
if not df_all.empty and current_file_hash:
    if st.session_state.last_file_hash != current_file_hash:
        st.session_state.last_file_hash = current_file_hash
    st.session_state.pending_file_update = False

# Simple error message for empty data
if df_all.empty:
    st.error("❌ No data available. Please contact the administrator to ensure data files are properly configured.")
    st.stop()

# File Upload Section in Sidebar (if Google Drive is available)
if use_google_drive and storage:
    st.sidebar.header("📤 Upload Excel Files")
    
    uploaded_file = st.sidebar.file_uploader(
        "Choose an Excel file",
        type=['xlsx', 'xls'],
        help="Upload Excel files to Google Drive. Files will be automatically processed."
    )
    
    if uploaded_file is not None:
        # Validate file
        is_valid, error_msg = validate_excel_file(uploaded_file)
        
        if is_valid:
            # Show upload button
            if st.sidebar.button("📤 Upload to Google Drive", type="primary"):
                try:
                    with st.sidebar.spinner("Uploading file..."):
                        # Read file data
                        file_data = uploaded_file.getvalue()
                        
                        # Upload to Google Drive
                        file_id = storage.upload_file(file_data, uploaded_file.name)
                        
                        if file_id:
                            st.sidebar.success(f"✅ File '{uploaded_file.name}' uploaded successfully!")
                            st.session_state.upload_success = True
                            st.session_state.refresh_requested = True
                            
                            # Clear cache to force reload
                            load_all_files.clear()
                            
                            # Auto-refresh after a moment
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.sidebar.error("❌ Failed to upload file. Please try again.")
                            st.session_state.upload_success = False
                except Exception as e:
                    st.sidebar.error(f"❌ Error uploading file: {str(e)}")
                    st.session_state.upload_success = False
        else:
            st.sidebar.error(f"❌ {error_msg}")
    
    # Show upload status
    if st.session_state.upload_success:
        st.sidebar.info("💡 File uploaded! Click 'Reload Data' to see changes.")
    
    st.sidebar.divider()
    
    # Show Google Drive status
    try:
        drive_files = storage.list_files()
        st.sidebar.info(f"📁 {len(drive_files)} file(s) in Google Drive")
    except:
        pass

# Filters sidebar
st.sidebar.header("🔍 Filters")

# Date range filter
min_date = df_all["__date"].min()
max_date = df_all["__date"].max()
if pd.notna(min_date) and pd.notna(max_date):
    date_range = st.sidebar.date_input(
        "📅 Date range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
        help="Select date range to filter data"
    )
else:
    date_range = st.sidebar.date_input("📅 Date range", value=None)
    st.sidebar.warning("⚠️ No valid dates found in files")

# Sub Division filter
subdivision_options = sorted(df_all["Sub Division"].dropna().unique().astype(str))
selected_subdivisions = st.sidebar.multiselect(
    "🏢 Sub Division",
    options=subdivision_options,
    default=None,
    help="Select one or more sub-divisions"
)

# Tehsil filter
if "Tehsil/Sub Tehsil" in df_all.columns:
    tehsil_options = sorted(df_all["Tehsil/Sub Tehsil"].dropna().unique().astype(str))
    selected_tehsils = st.sidebar.multiselect(
        "📍 Tehsil/Sub Tehsil",
        options=tehsil_options,
        default=None,
        help="Select one or more tehsils"
    )
else:
    selected_tehsils = None

# Officer filter
officer_options = sorted(df_all["Officer"].dropna().unique().astype(str))
selected_officers = st.sidebar.multiselect(
    "👤 Officer",
    options=officer_options,
    default=None,
    help="Select one or more officers"
)

# Group by option
group_by = st.sidebar.selectbox(
    "📊 Group by",
    options=["Sub Division", "Officer"],
    index=0,
    help="Choose grouping for aggregations"
)


# Developer credit in sidebar
st.sidebar.divider()
st.sidebar.markdown(
    "<div style='text-align: center; padding: 15px 0;'>"
    "<p style='margin: 0; color: #666; font-size: 0.85em; line-height: 1.5;'>"
    "Developed by<br>"
    "<strong style='color: #1f77b4; font-size: 1.1em;'>Shivam Gulati</strong><br>"
    "<span style='font-size: 0.8em;'>Land Revenue Fellow</span>"
    "</p></div>",
    unsafe_allow_html=True
)

# Apply filters
df = df_all.copy()
filter_applied = False

if date_range and len(date_range) == 2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    df = df[(df["__date"] >= start) & (df["__date"] <= end)]
    filter_applied = True

if selected_subdivisions:
    df = df[df["Sub Division"].astype(str).isin(selected_subdivisions)]
    filter_applied = True

if selected_tehsils and "Tehsil/Sub Tehsil" in df.columns:
    df = df[df["Tehsil/Sub Tehsil"].astype(str).isin(selected_tehsils)]
    filter_applied = True

if selected_officers:
    df = df[df["Officer"].astype(str).isin(selected_officers)]
    filter_applied = True


# Aggregate for visuals
agg_by_sub = df.groupby(["__date", "Sub Division"], as_index=False)["Total"].sum()
latest_date = df["__date"].max()
latest_snapshot = df[df["__date"] == latest_date].copy() if pd.notna(latest_date) else pd.DataFrame()

# Calculate previous period for comparison
previous_date = None
previous_snapshot = pd.DataFrame()
if not df.empty and pd.notna(latest_date):
    previous_date_options = df[df["__date"] < latest_date]["__date"].unique()
    if len(previous_date_options) > 0:
        previous_date = pd.to_datetime(previous_date_options.max())
        previous_snapshot = df[df["__date"] == previous_date].copy()

# Create tabs
tab1, tab2 = st.tabs(["📊 Executive Dashboard", "📈 Summary View"])

# ========== TAB 1: EXECUTIVE DASHBOARD ==========
with tab1:
    st.header("🎯 Executive Dashboard - At a Glance")
    
    if latest_snapshot.empty:
        st.warning("No data available for the selected date range/filters.")
    else:
        # Calculate key metrics
        total_latest = int(latest_snapshot["Total"].sum())
        total_previous = int(previous_snapshot["Total"].sum()) if not previous_snapshot.empty else 0
        total_change = calculate_change(total_latest, total_previous)
        
        num_subdivisions = latest_snapshot["Sub Division"].nunique()
        num_officers = latest_snapshot["Officer"].nunique()
        avg_per_subdivision = total_latest / num_subdivisions if num_subdivisions > 0 else 0
        
        # Top 3 sub-divisions
        snapshot_grouped = latest_snapshot.groupby("Sub Division", as_index=False)["Total"].sum().sort_values("Total", ascending=False)
        top3_subdivisions = snapshot_grouped.head(3)
        
        # Alerts
        alert_df = latest_snapshot[latest_snapshot["Total"] > threshold]
        num_alerts = alert_df["Sub Division"].nunique() if not alert_df.empty else 0
        
        # Top pendency type
        pendency_columns = [
            "Uncontested Pendency", "Income Certificate", "Copying Service",
            "Inspection Records", "Overdue Mortgage", "Overdue Court Orders",
            "Overdue Fardbadars"
        ]
        available_pendency_cols = [col for col in pendency_columns if col in latest_snapshot.columns]
        pendency_totals = {}
        for col in available_pendency_cols:
            pendency_totals[col] = int(latest_snapshot[col].sum())
        top_pendency_type = max(pendency_totals.items(), key=lambda x: x[1]) if pendency_totals else ("N/A", 0)
        
        # Key Metrics Row - Clean
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            delta_text = f"{total_change:+.1f}%" if previous_date else None
            delta_color = "inverse" if total_change > 0 else "normal"
            st.metric("Total Pendency", format_number(total_latest), delta=delta_text, delta_color=delta_color)
            if previous_date:
                st.caption(f"vs {previous_date.strftime('%b %d')}")
        
        with col2:
            st.metric("Sub Divisions", num_subdivisions)
            st.caption("Active divisions")
        
        with col3:
            st.metric("Avg per Division", format_number(avg_per_subdivision))
            st.caption("Average pendency")
        
        with col4:
            if num_alerts > 0:
                st.metric("⚠️ Alerts", num_alerts, delta=f"Above {threshold}", delta_color="inverse")
            else:
                st.metric("✅ Alerts", "0", delta="All clear")
            st.caption(f"Threshold: {threshold}")
        
        # Pendency Breakdown Section
        if available_pendency_cols and pendency_totals:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### 📋 Pendency Breakdown by Type")
            
            # Dropdown filter section
            filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 1])
            
            with filter_col1:
                # Get unique tehsils from latest snapshot
                if "Tehsil/Sub Tehsil" in latest_snapshot.columns:
                    tehsil_options = ["All"] + sorted(latest_snapshot["Tehsil/Sub Tehsil"].dropna().unique().astype(str).tolist())
                    selected_tehsil = st.selectbox(
                        "📍 Select Sub Tehsil",
                        options=tehsil_options,
                        index=0,
                        key="pendency_tehsil_filter"
                    )
                else:
                    selected_tehsil = "All"
                    st.selectbox(
                        "📍 Select Sub Tehsil",
                        options=["All"],
                        index=0,
                        key="pendency_tehsil_filter",
                        disabled=True
                    )
            
            with filter_col2:
                pendency_type_options = ["All"] + available_pendency_cols
                selected_pendency_type = st.selectbox(
                    "📊 Select Pendency Type",
                    options=pendency_type_options,
                    index=0,
                    key="pendency_type_filter"
                )
            
            with filter_col3:
                st.markdown("<br>", unsafe_allow_html=True)  # Spacing
                # Calculate and display the count
                filtered_data = latest_snapshot.copy()
                
                # Filter by tehsil
                if selected_tehsil != "All" and "Tehsil/Sub Tehsil" in filtered_data.columns:
                    filtered_data = filtered_data[filtered_data["Tehsil/Sub Tehsil"].astype(str) == selected_tehsil]
                
                # Calculate count based on pendency type
                if selected_pendency_type != "All":
                    if selected_pendency_type in filtered_data.columns:
                        count = int(filtered_data[selected_pendency_type].sum())
                    else:
                        count = 0
                else:
                    # If "All" pendency types, show total
                    count = int(filtered_data["Total"].sum())
                
                # Display count in a styled box
                st.markdown(
                    f"""
                    <div style="
                        background: linear-gradient(135deg, #0066cc 0%, #004488 100%);
                        padding: 0.8rem 1rem;
                        border-radius: 6px;
                        border-left: 4px solid #003366;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                        text-align: center;
                    ">
                        <p style="color: white; margin: 0; font-size: 0.75rem; font-weight: 600; opacity: 0.9;">
                            Count
                        </p>
                        <p style="color: white; margin: 0.25rem 0 0 0; font-size: 1.5rem; font-weight: 700;">
                            {format_number(count)}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Sort pendency types by value (descending)
            sorted_pendencies = sorted(pendency_totals.items(), key=lambda x: x[1], reverse=True)
            
            # Color gradient from light to dark (YlOrRd scale)
            colors = ['#ffffcc', '#ffeda0', '#fed976', '#feb24c', '#fd8d3c', '#fc4e2a', '#e31a1c', '#bd0026', '#800026']
            
            # Display in organized card layout
            num_pendencies = len(sorted_pendencies)
            cols_per_row = 4 if num_pendencies > 4 else num_pendencies
            
            for i in range(0, num_pendencies, cols_per_row):
                row_pendencies = sorted_pendencies[i:i+cols_per_row]
                cols = st.columns(len(row_pendencies))
                
                for col_idx, (pendency_type, pendency_value) in enumerate(row_pendencies):
                    with cols[col_idx]:
                        pct_of_total = (pendency_value / total_latest * 100) if total_latest > 0 else 0
                        
                        # Determine color based on percentage (darker for higher values)
                        color_idx = min(int(pct_of_total / 15), len(colors) - 1) if total_latest > 0 else 0
                        bg_color = colors[color_idx]
                        text_color = '#000000' if color_idx < 4 else '#ffffff'
                        
                        # Create compact styled card
                        st.markdown(
                            f"""
                            <div style="
                                background: linear-gradient(135deg, {bg_color} 0%, {colors[min(color_idx+1, len(colors)-1)]} 100%);
                                padding: 0.6rem 0.8rem;
                                border-radius: 6px;
                                border-left: 3px solid {colors[min(color_idx+2, len(colors)-1)]};
                                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                                margin-bottom: 0.5rem;
                            ">
                                <h4 style="color: {text_color}; margin: 0 0 0.3rem 0; font-size: 0.8rem; font-weight: 600; line-height: 1.2;">
                                    {pendency_type}
                                </h4>
                                <p style="color: {text_color}; margin: 0; font-size: 1.2rem; font-weight: 700; line-height: 1.2;">
                                    {format_number(pendency_value)}
                                </p>
                                <p style="color: {text_color}; margin: 0.15rem 0 0 0; font-size: 0.75rem; opacity: 0.9; line-height: 1.2;">
                                    {pct_of_total:.1f}%
                                </p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
        
        st.divider()
        
        # Quick Insights Row
        col_left, col_right = st.columns([2, 1])
        
        with col_left:
            st.markdown("### 📊 Top 3 Sub Divisions by Pendency")
            if not top3_subdivisions.empty:
                # Define distinct colors for top 3 (Gold, Silver, Bronze)
                subdivision_colors = ["#FFD700", "#C0C0C0", "#CD7F32"]  # Gold, Silver, Bronze
                
                for rank_idx, (idx, row) in enumerate(top3_subdivisions.iterrows()):
                    subdiv = row["Sub Division"]
                    total_val = int(row["Total"])
                    pct_of_total = (total_val / total_latest * 100) if total_latest > 0 else 0
                    progress_color = subdivision_colors[rank_idx] if rank_idx < 3 else subdivision_colors[2]
                    
                    # Calculate change for this sub-division
                    prev_val = 0
                    if not previous_snapshot.empty:
                        prev_subdiv = previous_snapshot[previous_snapshot["Sub Division"] == subdiv]
                        prev_val = int(prev_subdiv["Total"].sum()) if not prev_subdiv.empty else 0
                    subdiv_change = calculate_change(total_val, prev_val)
                    
                    
                    col_metric, col_bar = st.columns([3, 2])
                    with col_metric:
                        st.markdown(f"<p style='font-weight: 600; color: #003366; margin: 0.25rem 0; font-size: 1rem;'>{subdiv}</p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size: 1rem; color: #333; margin: 0.25rem 0;'><strong>{format_number(total_val)}</strong> <span style='color: #666; font-size: 0.85rem;'>({pct_of_total:.1f}% of total)</span></p>", unsafe_allow_html=True)
                        if previous_date:
                            change_icon = get_trend_icon(subdiv_change)
                            change_color = "#dc3545" if subdiv_change > 0 else "#28a745"
                            st.markdown(f"<p style='color: {change_color}; font-size: 0.85rem; margin: 0.25rem 0;'>{change_icon} {subdiv_change:+.1f}% vs previous</p>", unsafe_allow_html=True)
                    with col_bar:
                        # Custom colored progress bar
                        progress_value = min(pct_of_total / 100, 1.0)
                        st.markdown(
                            f"""
                            <div style="
                                width: 100%;
                                height: 1.5rem;
                                background-color: #e0e0e0;
                                border-radius: 0.25rem;
                                overflow: hidden;
                                margin-top: 0.5rem;
                            ">
                                <div style="
                                    width: {progress_value * 100}%;
                                    height: 100%;
                                    background-color: {progress_color};
                                    transition: width 0.3s ease;
                                "></div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
            else:
                st.info("No data available")
            
            # Top Officers with Most Pendencies
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### 👤 Top 5 Officers by Pendency")
            if not latest_snapshot.empty:
                # Sort by Total descending and take top 5 rows
                # Each row represents a unique officer-location combination
                top_officers = latest_snapshot.nlargest(5, "Total")
                
                if not top_officers.empty:
                    # Define distinct colors for top 5 officers
                    officer_colors = ["#FF6B6B", "#4ECDC4", "#95E1D3", "#F38181", "#AA96DA"]  # Red, Teal, Mint, Coral, Purple
                    
                    # Display in clean format
                    for rank_idx, (idx, row) in enumerate(top_officers.iterrows()):
                        officer = row["Officer"]
                        officer_total = int(row["Total"])
                        subdiv = row.get("Sub Division", "Unknown")
                        tehsil = row.get("Tehsil/Sub Tehsil", "N/A") if pd.notna(row.get("Tehsil/Sub Tehsil", None)) else "N/A"
                        pct_of_total = (officer_total / total_latest * 100) if total_latest > 0 else 0
                        progress_color = officer_colors[rank_idx] if rank_idx < 5 else officer_colors[4]
                        
                        
                        col_officer, col_officer_bar = st.columns([3, 2])
                        with col_officer:
                            st.markdown(f"<p style='font-size: 0.95rem; font-weight: 600; color: #003366; margin: 0.25rem 0;'><strong>{subdiv}</strong> - <strong>{tehsil}</strong> - <strong>{officer}</strong></p>", unsafe_allow_html=True)
                            st.markdown(f"<p style='font-size: 1rem; color: #333; margin: 0.25rem 0;'><strong>{format_number(officer_total)}</strong> <span style='color: #666; font-size: 0.85rem;'>({pct_of_total:.1f}% of total)</span></p>", unsafe_allow_html=True)
                        with col_officer_bar:
                            # Custom colored progress bar
                            progress_value = min(pct_of_total / 100, 1.0)
                            st.markdown(
                                f"""
                                <div style="
                                    width: 100%;
                                    height: 1.5rem;
                                    background-color: #e0e0e0;
                                    border-radius: 0.25rem;
                                    overflow: hidden;
                                    margin-top: 0.5rem;
                                ">
                                    <div style="
                                        width: {progress_value * 100}%;
                                        height: 100%;
                                        background-color: {progress_color};
                                        transition: width 0.3s ease;
                                    "></div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                else:
                    st.info("No officer data available")
            else:
                st.info("No data available")
        
        with col_right:
            st.markdown("### 🔥 Critical Issues")
            
            # Top pendency type - clear styling
            if top_pendency_type[0] != "N/A":
                st.markdown(f"<p style='font-weight: 600; color: #003366; margin: 0.5rem 0;'>Top Issue:</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='font-size: 1rem; font-weight: 600; color: #333; margin: 0.5rem 0;'>{top_pendency_type[0]}</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='font-size: 1.2rem; font-weight: 700; color: #003366; margin: 0.5rem 0;'>{format_number(top_pendency_type[1])}</p>", unsafe_allow_html=True)
                pct = (top_pendency_type[1] / total_latest * 100) if total_latest > 0 else 0
                st.caption(f"{pct:.1f}% of total")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Top alert sub-division - clear styling
            if not alert_df.empty:
                top_alert = alert_df.groupby("Sub Division", as_index=False)["Total"].sum().sort_values("Total", ascending=False).head(1)
                if not top_alert.empty:
                    st.markdown(f"<p style='font-weight: 600; color: #003366; margin: 0.5rem 0;'>Highest Alert:</p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='font-size: 1rem; font-weight: 600; color: #333; margin: 0.5rem 0;'>{top_alert.iloc[0]['Sub Division']}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='font-size: 1.2rem; font-weight: 700; color: #003366; margin: 0.5rem 0;'>{format_number(int(top_alert.iloc[0]['Total']))}</p>", unsafe_allow_html=True)
                    st.caption(f"{int(top_alert.iloc[0]['Total']) - threshold} above threshold")
            else:
                st.markdown("""
                <div style="background-color: #f0fff4; padding: 1.25rem; border: 1px solid #c3e6cb; border-left: 4px solid #28a745; border-radius: 4px;">
                    <p style='font-size: 0.95rem; font-weight: 600; color: #155724; margin: 0;'>✅ No critical alerts</p>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Visual Insights
        col_viz1, col_viz2 = st.columns(2)
        
        with col_viz1:
            st.markdown("### 📈 Trend Overview")
            total_trend = agg_by_sub.groupby("__date", as_index=False)["Total"].sum().sort_values("__date")
            if not total_trend.empty and len(total_trend) > 1:
                fig_trend = px.line(
                    total_trend, x="__date", y="Total", markers=True,
                    title="District Total Trend",
                    color_discrete_sequence=['#1f77b4']
                )
                fig_trend.add_scatter(
                    x=total_trend["__date"], y=total_trend["Total"],
                    mode='lines+markers', name='Trend',
                    line=dict(width=3, color='#1f77b4'),
                    marker=dict(size=8, color='#1f77b4')
                )
                fig_trend.update_layout(
                    height=300,
                    showlegend=False,
                    xaxis_title="Date",
                    yaxis_title="Total Pendency",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    autosize=True,
                    margin=dict(l=50, r=20, t=30, b=50),
                    xaxis=dict(
                        dtick=86400000,  # Daily scale (milliseconds in a day)
                        tickformat="%Y-%m-%d",  # Date format
                        tickmode="linear",
                        gridcolor='rgba(128,128,128,0.2)'
                    ),
                    yaxis=dict(gridcolor='rgba(128,128,128,0.2)')
                )
                st.plotly_chart(fig_trend, use_container_width=True, config={'displayModeBar': False, 'responsive': True})
            else:
                st.info("Insufficient data for trend")
        
        with col_viz2:
            st.markdown("### 🗺️ Pendency Distribution")
            if not snapshot_grouped.empty:
                # Create a more visual bar chart
                fig_dist = px.bar(
                    snapshot_grouped.head(10), x="Sub Division", y="Total",
                    title="Top 10 Sub Divisions",
                    color="Total",
                    color_continuous_scale="Reds",
                    text="Total"
                )
                fig_dist.update_traces(texttemplate='%{text:,}', textposition='outside')
                fig_dist.update_layout(
                    height=300,
                    showlegend=False,
                    xaxis_title="Sub Division",
                    yaxis_title="Total Pendency",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    autosize=True,
                    margin=dict(l=50, r=20, t=30, b=80),
                    xaxis={'categoryorder': 'total descending', 'gridcolor': 'rgba(128,128,128,0.2)'},
                    yaxis={'gridcolor': 'rgba(128,128,128,0.2)'}
                )
                fig_dist.update_xaxes(tickangle=45)
                st.plotly_chart(fig_dist, use_container_width=True, config={'displayModeBar': False, 'responsive': True})
            else:
                st.info("No data available")
        
        # Heatmap: Sub Division vs Pendency Types
        if available_pendency_cols and not latest_snapshot.empty:
            st.markdown("### 🔥 Heatmap: Sub Division vs Pendency Types")
            heatmap_data = []
            for subdiv in latest_snapshot["Sub Division"].dropna().unique()[:15]:  # Top 15
                subdiv_df = latest_snapshot[latest_snapshot["Sub Division"] == subdiv]
                row = {"Sub Division": subdiv}
                for pcol in available_pendency_cols:
                    row[pcol] = int(subdiv_df[pcol].sum())
                heatmap_data.append(row)
            
            if heatmap_data:
                heatmap_df = pd.DataFrame(heatmap_data)
                heatmap_df = heatmap_df.set_index("Sub Division")
                
                # Create heatmap with better color contrast
                fig_heatmap = px.imshow(
                    heatmap_df.T,
                    labels=dict(x="Sub Division", y="Pendency Type", color="Count"),
                    aspect="auto",
                    color_continuous_scale="YlOrRd",  # Light (yellow) to Dark (red) - light for low, dark for high
                    title="Pendency Hotspots by Type and Sub Division",
                    text_auto=True
                )
                fig_heatmap.update_layout(
                    height=400,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    autosize=True,
                    margin=dict(l=100, r=20, t=40, b=100)
                )
                # Add colorbar title for clarity
                fig_heatmap.update_coloraxes(colorbar_title="Pendency Count")
                st.plotly_chart(fig_heatmap, use_container_width=True, config={'displayModeBar': False, 'responsive': True})
                
                # Add expandable section with officer details
                with st.expander("📋 View Officers Responsible for Each Sub-Division and Pendency Type"):
                    officer_details = []
                    for subdiv in latest_snapshot["Sub Division"].dropna().unique()[:15]:
                        subdiv_df = latest_snapshot[latest_snapshot["Sub Division"] == subdiv]
                        for pcol in available_pendency_cols:
                            officers_with_pendency = subdiv_df[subdiv_df[pcol] > 0]
                            if not officers_with_pendency.empty:
                                for _, row in officers_with_pendency.iterrows():
                                    officer_details.append({
                                        "Pendency Type": pcol,
                                        "Officer": row["Officer"],
                                        "Tehsil/Sub Tehsil": row.get("Tehsil/Sub Tehsil", "N/A") if pd.notna(row.get("Tehsil/Sub Tehsil", None)) else "N/A",
                                        "Count": int(row[pcol])
                                    })
                    
                    if officer_details:
                        details_df = pd.DataFrame(officer_details)
                        # Reorder columns: Tehsil first, then Pendency Type, Officer, Count
                        details_df = details_df[["Tehsil/Sub Tehsil", "Pendency Type", "Officer", "Count"]]
                        # Sort by Pendency Type and Count
                        details_df = details_df.sort_values(["Pendency Type", "Count"], ascending=[True, False])
                        st.dataframe(details_df, width='stretch', hide_index=True, height=400)
                    else:
                        st.info("No officer details available")
        
        # Quick Action Items
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### ⚡ Quick Insights")
        insights_col1, insights_col2, insights_col3 = st.columns(3)
        
        with insights_col1:
            st.write("**📊 Pendency Breakdown**")
            if pendency_totals:
                sorted_pendencies = sorted(pendency_totals.items(), key=lambda x: x[1], reverse=True)
                for ptype, pval in sorted_pendencies[:3]:
                    pct = (pval / total_latest * 100) if total_latest > 0 else 0
                    st.write(f"• {ptype}: {format_number(pval)} ({pct:.1f}%)")
        
        with insights_col2:
            st.write("**📍 Geographic Spread**")
            if not snapshot_grouped.empty:
                top_div = snapshot_grouped.iloc[0]
                bottom_div = snapshot_grouped.iloc[-1]
                st.write(f"• Highest: **{top_div['Sub Division']}** ({format_number(top_div['Total'])})")
                st.write(f"• Lowest: **{bottom_div['Sub Division']}** ({format_number(bottom_div['Total'])})")
                spread = top_div['Total'] - bottom_div['Total']
                st.caption(f"Range: {format_number(spread)}")
        
        with insights_col3:
            st.write("**📈 Performance**")
            if previous_date:
                st.write(f"• Period Change: {total_change:+.1f}%")
                st.write(f"• Date Range: {previous_date.strftime('%b %d')} → {latest_date.strftime('%b %d')}")
            else:
                st.write("• No previous period data")
            if num_alerts > 0:
                st.write(f"• ⚠️ {num_alerts} division(s) need attention")

# ========== TAB 2: SUMMARY VIEW ==========
with tab2:
    st.markdown("## 📈 Total Pendency Summary")
    
    # Group by Sub Division for charts
    snapshot_grouped = latest_snapshot.groupby("Sub Division", as_index=False)["Total"].sum().sort_values("Total", ascending=False)

    # Layout: Left charts, right KPIs
    left, right = st.columns([3,1])

    with left:
        # Bar chart: Total pendency by Sub Division (latest)
        st.markdown(f"### 📊 Total Pendency by Sub Division — {latest_date.date() if pd.notna(latest_date) else 'Latest'}")
        if not snapshot_grouped.empty:
            fig_bar = px.bar(
                snapshot_grouped, x="Sub Division", y="Total",
                title="Total by Sub Division",
                labels={"Total": "Total Pendency"},
                color="Total",
                color_continuous_scale="Blues",
                text="Total"
            )
            fig_bar.update_traces(texttemplate='%{text:,}', textposition='outside')
            fig_bar.update_layout(
                xaxis={'categoryorder': 'total descending'},
                height=450,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                autosize=True,
                margin=dict(l=50, r=20, t=30, b=100),
                xaxis_gridcolor='rgba(128,128,128,0.2)',
                yaxis_gridcolor='rgba(128,128,128,0.2)'
            )
            fig_bar.update_xaxes(tickangle=45)
            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False, 'responsive': True})
        else:
            st.info("No data for the selected date range/filters.")

        # Trend
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 📈 District Total Trend")
        total_trend = agg_by_sub.groupby("__date", as_index=False)["Total"].sum().sort_values("__date")
        if not total_trend.empty:
            fig_line = px.line(
                total_trend, x="__date", y="Total", markers=True,
                title="Total Pendency over time",
                color_discrete_sequence=['#2E86AB']
            )
            fig_line.update_traces(
                line=dict(width=3),
                marker=dict(size=8)
            )
            fig_line.update_layout(
                xaxis_title="Date",
                yaxis_title="Total Pendency",
                height=350,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                autosize=True,
                margin=dict(l=50, r=20, t=30, b=50),
                xaxis=dict(
                    dtick=86400000,  # Daily scale (milliseconds in a day)
                    tickformat="%Y-%m-%d",  # Date format
                    tickmode="linear",
                    gridcolor='rgba(128,128,128,0.2)'
                ),
                yaxis=dict(gridcolor='rgba(128,128,128,0.2)')
            )
            st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': False, 'responsive': True})
        else:
            st.info("No trend data for the selected date range/filters.")
        
        # Pendency Types Breakdown by Sub Division
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 📊 Pendency Types Breakdown by Sub Division")
        
        # Get available pendency columns
        pendency_columns = [
            "Uncontested Pendency", "Income Certificate", "Copying Service",
            "Inspection Records", "Overdue Mortgage", "Overdue Court Orders",
            "Overdue Fardbadars"
        ]
        available_pendency_cols = [col for col in pendency_columns if col in latest_snapshot.columns]
        
        if available_pendency_cols and not latest_snapshot.empty:
            # Prepare data for stacked bar chart
            breakdown_data = []
            for subdiv in latest_snapshot["Sub Division"].dropna().unique():
                subdiv_df = latest_snapshot[latest_snapshot["Sub Division"] == subdiv]
                row = {"Sub Division": subdiv}
                for pcol in available_pendency_cols:
                    row[pcol] = int(subdiv_df[pcol].sum())
                breakdown_data.append(row)
            
            if breakdown_data:
                breakdown_df = pd.DataFrame(breakdown_data)
                # Sort by total pendency (descending)
                breakdown_df["Total"] = breakdown_df[available_pendency_cols].sum(axis=1)
                breakdown_df = breakdown_df.sort_values("Total", ascending=False).head(15)  # Top 15
                breakdown_df = breakdown_df.drop("Total", axis=1)
                
                # Create stacked bar chart
                fig_stacked = px.bar(
                    breakdown_df,
                    x="Sub Division",
                    y=available_pendency_cols,
                    title="Pendency Types Distribution by Sub Division",
                    labels={"value": "Pendency Count", "Sub Division": "Sub Division"},
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_stacked.update_layout(
                    xaxis={'categoryorder': 'total descending'},
                    height=450,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    autosize=True,
                    margin=dict(l=50, r=120, t=30, b=100),
                    xaxis_gridcolor='rgba(128,128,128,0.2)',
                    yaxis_gridcolor='rgba(128,128,128,0.2)',
                    legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
                )
                # Adjust legend for mobile (horizontal at bottom) vs desktop (vertical on right)
                # CSS will handle responsive legend positioning
                fig_stacked.update_xaxes(tickangle=45)
                st.plotly_chart(fig_stacked, use_container_width=True, config={'displayModeBar': False, 'responsive': True})
            else:
                st.info("No breakdown data available")
        else:
            st.info("Pendency type data not available")

    with right:
        st.markdown("### 📊 Key Metrics")
        total_latest = int(latest_snapshot["Total"].sum()) if not latest_snapshot.empty else 0
        total_previous = int(previous_snapshot["Total"].sum()) if not previous_snapshot.empty else 0
        total_change = calculate_change(total_latest, total_previous)
        
        # Metrics with trends
        delta_text = f"{total_change:+.1f}%" if previous_date else None
        delta_color = "inverse" if total_change > 0 else "normal"
        st.metric("District Total", format_number(total_latest), delta=delta_text, delta_color=delta_color)
        if previous_date:
            st.caption(f"vs {previous_date.strftime('%b %d')}")
        
        st.metric("Sub Divisions", latest_snapshot["Sub Division"].nunique())
        st.metric("Officers", latest_snapshot["Officer"].nunique())
        
        # Alerts
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### ⚠️ Alerts")
        alert_df = latest_snapshot[latest_snapshot["Total"] > threshold]
        if not alert_df.empty:
            num_alerts = alert_df["Sub Division"].nunique()
            st.metric("Alerts", num_alerts, delta=f"Above {threshold}", delta_color="inverse")
            # show top 5 alerts with percentage
            alerts = alert_df.groupby("Sub Division", as_index=False)["Total"].sum().sort_values("Total", ascending=False).head(5)
            alerts["% of Total"] = (alerts["Total"] / total_latest * 100).round(1)
            alerts["Above Threshold"] = alerts["Total"] - threshold
            display_alerts = alerts[["Sub Division", "Total", "% of Total", "Above Threshold"]]
            st.dataframe(display_alerts, width='stretch', hide_index=True)
        else:
            st.success(f"✅ No alerts (all below {threshold})")

    # Comprehensive Summary Table
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📋 Complete Summary Table")
    
    if not latest_snapshot.empty:
        total_latest = int(latest_snapshot["Total"].sum())
        
        # Create comprehensive summary table
        summary_table = latest_snapshot.copy()
        
        # Define pendency columns
        pendency_columns = [
            "Uncontested Pendency", "Income Certificate", "Copying Service",
            "Inspection Records", "Overdue Mortgage", "Overdue Court Orders",
            "Overdue Fardbadars"
        ]
        available_pendency_cols = [col for col in pendency_columns if col in summary_table.columns]
        
        # Add percentage column
        summary_table["% of Total"] = (summary_table["Total"] / total_latest * 100).round(2)
        
        # Add rank if not present
        if "Rank" not in summary_table.columns:
            summary_table["Rank"] = summary_table["Total"].rank(ascending=False, method="dense").astype(int)
        
        # Add alert indicator
        summary_table["Alert"] = summary_table["Total"].apply(lambda x: "⚠️" if x > threshold else "✅")
        
        # Select and order columns for display
        display_cols = []
        
        # Core identification columns
        if "Rank" in summary_table.columns:
            display_cols.append("Rank")
        display_cols.append("Sub Division")
        if "Tehsil/Sub Tehsil" in summary_table.columns:
            display_cols.append("Tehsil/Sub Tehsil")
        display_cols.append("Officer")
        
        # Add all pendency type columns
        for col in available_pendency_cols:
            display_cols.append(col)
        
        # Add summary columns
        display_cols.extend(["Total", "% of Total", "Alert"])
        
        # Create final table
        final_table = summary_table[display_cols].copy()
        
        # Sort by Total descending (before formatting)
        final_table = final_table.sort_values("Total", ascending=False).reset_index(drop=True)
        
        # Format numeric columns for display
        final_table_display = final_table.copy()
        for col in available_pendency_cols + ["Total"]:
            if col in final_table_display.columns:
                final_table_display[col] = final_table_display[col].apply(format_number)
        
        # Format percentage
        if "% of Total" in final_table_display.columns:
            final_table_display["% of Total"] = final_table_display["% of Total"].apply(lambda x: f"{x:.2f}%")
        
        # Add summary statistics row
        st.markdown(f"**Total Records:** {len(final_table_display)} | **Date:** {latest_date.strftime('%B %d, %Y') if pd.notna(latest_date) else 'Latest'}")
        
        # Display table with search and sort
        st.dataframe(
            final_table_display,
                width='stretch',
            hide_index=True,
            height=400
        )
        
        # Download buttons
        col_download1, col_download2 = st.columns(2)
        with col_download1:
            csv_formatted = final_table_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Formatted Table (CSV)",
                data=csv_formatted,
                file_name=f"fcr_summary_{latest_date.strftime('%Y%m%d')}.csv",
                mime="text/csv",
                width='stretch'
            )
        with col_download2:
            csv_raw = final_table.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Raw Data (CSV)",
                data=csv_raw,
                file_name=f"fcr_raw_{latest_date.strftime('%Y%m%d')}.csv",
                mime="text/csv",
                width='stretch'
            )
        
    else:
        st.info("No latest snapshot to display.")

    # Download full combined history
    st.subheader("Download Full Historical Data")
    hist_csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download full history CSV", data=hist_csv, file_name="fcr_history.csv")


# Footer - simplified
st.divider()
footer_col1, footer_col2, footer_col3 = st.columns([2, 1, 1])
with footer_col1:
    if not df_all.empty:
        dates = df_all["__date"].dropna().unique()
        if len(dates) > 0:
            date_range_str = f"{pd.to_datetime(dates.min()).strftime('%b %d, %Y')} to {pd.to_datetime(dates.max()).strftime('%b %d, %Y')}"
            st.caption(f"📅 Data period: {date_range_str}")
with footer_col2:
    st.caption(f"📊 Last refreshed: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
with footer_col3:
    st.markdown(
        "<div style='text-align: right; padding: 10px 0;'>"
        "<p style='margin: 0; color: #666; font-size: 0.9em;'>"
        "Developed by <strong style='color: #1f77b4;'>Shivam Gulati</strong><br>"
        "<span style='font-size: 0.85em;'>Land Revenue Fellow</span>"
        "</p></div>",
        unsafe_allow_html=True
    )