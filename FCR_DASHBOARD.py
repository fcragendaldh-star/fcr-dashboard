# app.py
"""
Streamlit FCR Dashboard with Google Drive Integration
Reads cleaned daily Excel files from Google Drive or local folder and shows:
- Total pendency by Sub Division (bar)
- Trend over time (line)
- Officer-level table with ranks
- Top/Bottom performers and alerts
- CSV export and download
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
google_drive_error = None

if GOOGLE_DRIVE_AVAILABLE:
    try:
        storage = GoogleDriveStorage()
        use_google_drive = True
        logger.info("✓ Google Drive storage initialized successfully")
    except ValueError as e:
        # Missing configuration (secrets not set)
        google_drive_error = str(e)
        logger.warning(f"⚠️ Google Drive not configured: {e}")
        use_google_drive = False
        DATA_FOLDER.mkdir(exist_ok=True)
    except Exception as e:
        # Other errors (API errors, network issues, etc.)
        google_drive_error = f"Failed to initialize: {str(e)}"
        logger.error(f"❌ Google Drive initialization error: {e}")
        use_google_drive = False
        DATA_FOLDER.mkdir(exist_ok=True)
else:
    DATA_FOLDER.mkdir(exist_ok=True)

# Initialize session state for settings persistence
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

# Core function to load and process Excel files from Google Drive or local
def _load_all_files_core(folder_path: str = None) -> pd.DataFrame:
    """Core function to load all Excel files from Google Drive or local folder and process them."""
    rows = []
    failed_files = []
    
    # Load from Google Drive if configured
    if use_google_drive and storage and folder_path is None:
        try:
            logger.info("Loading files from Google Drive...")
            drive_files = storage.list_files()
            
            if not drive_files:
                logger.info("No Excel files found in Google Drive folder")
                return pd.DataFrame()
            
            logger.info(f"Found {len(drive_files)} files in Google Drive")
            
            # Process each file from Google Drive
            for drive_file in drive_files:
                file_name = drive_file.get('name', '')
                file_id = drive_file.get('id', '')
                
                # Skip non-Excel files
                if not file_name.endswith(('.xlsx', '.xls')):
                    continue
                
                try:
                    # Download file from Google Drive
                    logger.info(f"Downloading file: {file_name}")
                    file_data = storage.download_file(file_id)
                    
                    if file_data.getvalue() == b'':
                        logger.warning(f"File {file_name} is empty, skipping")
                        failed_files.append((file_name, "Empty file"))
                        continue
                    
                    # Read Excel file from bytes
                    try:
                        df = pd.read_excel(file_data, engine="openpyxl")
                    except Exception as e:
                        logger.warning(f"Failed to read {file_name} with default sheet, trying first sheet: {e}")
                        file_data.seek(0)  # Reset file pointer
                        df = pd.read_excel(file_data, sheet_name=0, engine="openpyxl")
                    
                    if df.empty:
                        logger.warning(f"File {file_name} is empty, skipping")
                        failed_files.append((file_name, "Empty file"))
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
                    is_valid, error_msg = validate_dataframe(df, file_name)
                    if not is_valid:
                        logger.warning(f"Validation failed for {file_name}: {error_msg}")
                        failed_files.append((file_name, error_msg))
                        continue
                    
                    # Parse date from filename
                    m = FILENAME_DATE_RE.search(file_name)
                    file_date = pd.to_datetime(m.group(1), format=DATE_FORMAT) if m else pd.NaT
                    if pd.isna(file_date):
                        logger.warning(f"Could not parse date from filename: {file_name}")
                    
                    df["__source_file"] = file_name
                    df["__date"] = file_date
                    rows.append(df)
                    logger.info(f"Successfully processed file: {file_name}")
                
                except Exception as e:
                    logger.error(f"Error processing file {file_name} from Google Drive: {str(e)}")
                    failed_files.append((file_name, str(e)))
                    continue
            
            # If we successfully loaded files from Google Drive, skip local loading
            if rows:
                logger.info(f"Successfully loaded {len(rows)} files from Google Drive")
            elif failed_files:
                logger.error(f"All Google Drive files failed to load. Failed: {failed_files}")
                return pd.DataFrame()
            else:
                logger.warning("No files were processed from Google Drive")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error loading from Google Drive: {e}")
            # Fall back to local if Google Drive fails and folder_path is provided
            if folder_path:
                logger.info("Falling back to local file loading...")
            else:
                return pd.DataFrame()
    
    # Load from local folder if not using Google Drive or as fallback
    if not use_google_drive or (use_google_drive and not rows and folder_path):
        if folder_path:
            folder = Path(folder_path)
            if not folder.exists():
                logger.warning(f"Data folder does not exist: {folder}")
                if not rows:  # Only return empty if we have no data from Google Drive either
                    return pd.DataFrame()
            else:
                files = sorted(folder.glob("*.xlsx"))
                if not files:
                    logger.info(f"No Excel files found in {folder}")
                    if not rows:  # Only return empty if we have no data from Google Drive either
                        return pd.DataFrame()
                else:
                    # Process local files
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
                            logger.info(f"Successfully processed file: {f.name}")
                        
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
        div[data-testid="stDataFrame"],
        div[data-testid="stDataFrame"] > div {
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch;
            width: 100% !important;
            display: block !important;
        }
        
        /* Make table cells more readable on mobile */
        .dataframe th,
        .dataframe td {
            padding: 8px 6px !important;
            font-size: 0.8rem !important;
            white-space: nowrap;
        }
        
        /* Reduce table font size */
        .dataframe {
            font-size: 0.75rem !important;
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
            font-size: 10px !important;
        }
        
        /* Adjust chart heights for mobile */
        .js-plotly-plot {
            min-height: 250px !important;
            max-height: 400px !important;
        }
        
        /* Better margins for mobile charts */
        .plotly .plot-container {
            padding: 5px !important;
        }
        
        /* Reduce chart font sizes on mobile */
        .plotly .xtick text,
        .plotly .ytick text {
            font-size: 10px !important;
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
    
    /* Column layouts - optimize for mobile */
    @media screen and (max-width: 768px) {
        /* Metrics in 2x2 grid on mobile for better space usage */
        /* Target rows that contain metrics */
        .row-widget.stHorizontal {
            display: flex !important;
            flex-wrap: wrap !important;
            gap: 0.5rem !important;
        }
        
        /* For rows with exactly 4 columns (like Key Metrics), use 2x2 grid */
        .row-widget.stHorizontal [data-testid="column"]:nth-child(1),
        .row-widget.stHorizontal [data-testid="column"]:nth-child(2),
        .row-widget.stHorizontal [data-testid="column"]:nth-child(3),
        .row-widget.stHorizontal [data-testid="column"]:nth-child(4) {
            width: calc(50% - 0.25rem) !important;
            flex: 0 0 calc(50% - 0.25rem) !important;
            min-width: calc(50% - 0.25rem) !important;
            max-width: calc(50% - 0.25rem) !important;
            margin-bottom: 0.5rem !important;
            margin-right: 0 !important;
            padding: 0 !important;
        }
        
        /* Every 2nd column (2, 4, 6...) - no special treatment needed with gap */
        /* For rows with 2 or 3 columns, stack them */
        .row-widget.stHorizontal [data-testid="column"]:only-child,
        .row-widget.stHorizontal [data-testid="column"]:nth-child(n+5) {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
            max-width: 100% !important;
            margin-right: 0 !important;
        }
        
        /* Settings row and other non-metric rows - stack vertically */
        /* Use more specific selectors for better compatibility */
        .row-widget.stHorizontal [data-testid="column"] .stNumberInput,
        .row-widget.stHorizontal [data-testid="column"] .stButton,
        .row-widget.stHorizontal [data-testid="column"] .stSelectbox,
        .row-widget.stHorizontal [data-testid="column"] input,
        .row-widget.stHorizontal [data-testid="column"] button {
            width: 100% !important;
        }
        
        /* Force full width for columns containing inputs/buttons */
        .row-widget.stHorizontal [data-testid="column"]:has(.stNumberInput),
        .row-widget.stHorizontal [data-testid="column"]:has(.stButton),
        .row-widget.stHorizontal [data-testid="column"]:has(.stSelectbox) {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
            max-width: 100% !important;
            margin-right: 0 !important;
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
    
    /* Additional mobile optimizations */
    @media screen and (max-width: 768px) {
        /* Sidebar improvements */
        [data-testid="stSidebar"] {
            padding: 1rem 0.75rem !important;
        }
        
        /* Multiselect improvements for mobile */
        [data-baseweb="select"] {
            min-height: 44px !important;
        }
        
        [data-baseweb="select"] input {
            font-size: 16px !important;
            min-height: 44px !important;
        }
        
        /* Date input improvements */
        .stDateInput > div > div > input {
            font-size: 16px !important;
            min-height: 44px !important;
        }
        
        /* Number input improvements */
        .stNumberInput > div > div > input {
            font-size: 16px !important;
            min-height: 44px !important;
        }
        
        /* Tabs - make them more touch-friendly */
        [data-baseweb="tab-list"] {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        
        [data-baseweb="tab"] {
            min-width: 100px;
            padding: 0.75rem 1rem !important;
            font-size: 0.85rem !important;
        }
        
        /* Expander/collapsible sections */
        .streamlit-expanderHeader {
            font-size: 0.9rem !important;
            padding: 0.75rem !important;
            min-height: 44px !important;
        }
        
        /* Better spacing for download buttons */
        .stDownloadButton > button {
            width: 100% !important;
            margin-bottom: 0.5rem;
        }
        
        /* Alert and info boxes - better mobile display */
        .stAlert,
        .stInfo,
        .stSuccess,
        .stWarning,
        .stError {
            padding: 0.75rem !important;
            margin: 0.75rem 0 !important;
            font-size: 0.85rem !important;
            line-height: 1.5 !important;
        }
        
        /* Metrics - better spacing on mobile */
        [data-testid="stMetricContainer"] {
            padding: 0.5rem !important;
            margin-bottom: 0.5rem !important;
        }
        
        /* Compact metrics for 2x2 grid */
        [data-testid="stMetric"] {
            padding: 0.5rem !important;
        }
        
        [data-testid="stMetricValue"] {
            font-size: 1.3rem !important;
            line-height: 1.2 !important;
        }
        
        [data-testid="stMetricLabel"] {
            font-size: 0.75rem !important;
            margin-bottom: 0.25rem !important;
        }
        
        [data-testid="stMetricDelta"] {
            font-size: 0.7rem !important;
            margin-top: 0.25rem !important;
        }
        
        /* Ensure metric containers don't overflow */
        [data-testid="stMetricContainer"] {
            overflow: hidden !important;
        }
        
        /* Better spacing for metric cards in grid */
        [data-testid="column"] [data-testid="stMetricContainer"] {
            height: auto !important;
            min-height: 80px !important;
        }
        
        /* Reduce padding in main content area */
        .main .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
        }
        
        /* Improve caption readability */
        .stCaption {
            font-size: 0.7rem !important;
            line-height: 1.4 !important;
        }
        
        /* Better spacing for markdown content */
        .stMarkdown {
            margin-bottom: 0.75rem !important;
        }
        
        /* Ensure all text is readable */
        .stMarkdown p,
        .stMarkdown li,
        .stMarkdown span {
            font-size: 0.85rem !important;
            line-height: 1.6 !important;
        }
        
        /* Progress bars - better visibility */
        .stProgress > div {
            margin: 0.5rem 0 !important;
        }
        
        /* Hide unnecessary elements on mobile */
        .stApp > header {
            padding: 0.5rem 0.75rem !important;
        }
        
        /* Better button groups */
        .stButton {
            width: 100% !important;
            margin-bottom: 0.5rem !important;
        }
        
        /* Ensure horizontal scroll works for wide content */
        .element-container {
            overflow-x: visible !important;
        }
        
        /* Fix for plotly charts in columns */
        [data-testid="column"] .js-plotly-plot {
            width: 100% !important;
            max-width: 100% !important;
        }
    }
    
    /* Very small screens (phones in portrait) */
    @media screen and (max-width: 480px) {
        h1 {
            font-size: 1.2rem !important;
        }
        
        h2 {
            font-size: 1rem !important;
        }
        
        h3 {
            font-size: 0.9rem !important;
        }
        
        [data-testid="stMetricValue"] {
            font-size: 1.25rem !important;
        }
        
        .main .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        
        [data-testid="stSidebar"] {
            padding: 0.75rem 0.5rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# Use session state data folder (no user input needed)
data_folder = st.session_state.data_folder
DATA_FOLDER = Path(data_folder)

# Threshold is fixed at 50 (not user-configurable)
threshold = 50

# Prominent Header with Reload Button on Right
header_col1, header_col2 = st.columns([3, 1])
with header_col1:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #003366 0%, #0066cc 100%); padding: 1.5rem 2rem; margin-bottom: 1.5rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h1 style="color: #ffffff; margin: 0; padding: 0; border: none; font-size: 2rem; font-weight: 700; letter-spacing: 0.5px;">FCR Daily Dashboard</h1>
    </div>
    """, unsafe_allow_html=True)

with header_col2:
    st.markdown("<br>", unsafe_allow_html=True)  # Spacing for alignment
    # Beautiful reload button with custom styling
    st.markdown("""
    <style>
    div[data-testid="stButton"] > button[kind="primary"][data-baseweb="button"] {
        background-color: #ffffff !important;
        color: #003366 !important;
        border: 2px solid #ffffff !important;
        border-radius: 8px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
        width: 100% !important;
    }
    div[data-testid="stButton"] > button[kind="primary"][data-baseweb="button"]:hover {
        background-color: #f0f0f0 !important;
        color: #003366 !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.3) !important;
        transform: translateY(-2px) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    if st.button("🔄 Reload Data", type="primary", width='stretch', key="reload_button"):
        # Set flag in session state to persist across reruns
        st.session_state.refresh_requested = True
        st.rerun()
    
    refresh = st.session_state.get("refresh_requested", False)

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
    st.error("❌ No data available.")

    # Provide helpful troubleshooting based on storage type
    if use_google_drive and storage:
        st.info("""
        **Troubleshooting Google Drive:**
        1. Check that Excel files are uploaded to your Google Drive folder
        2. Verify files have `.xlsx` or `.xls` extension
        3. Ensure files contain required columns: `Sub Division`, `Officer`, `Total`
        4. Click "🔄 Reload Data" to refresh
        """)
    else:
        st.info("""
        **Troubleshooting:**
        1. Ensure Excel files are in the data folder
        2. Verify files have `.xlsx` or `.xls` extension
        3. Ensure files contain required columns: `Sub Division`, `Officer`, `Total`
        4. Click "🔄 Reload Data" to refresh
        """)
    
    st.stop()

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

# Add JavaScript to auto-close multiselect dropdowns and mobile optimizations
st.sidebar.markdown("""
<script>
(function() {
    // Enhanced function to close multiselect dropdowns
    function closeAllDropdowns() {
        try {
            // Get the parent document (Streamlit runs in iframe)
            const doc = window.parent !== window ? window.parent.document : document;
            
            // Method 1: Find and blur all active select inputs
            const selectInputs = doc.querySelectorAll('[data-baseweb="select"] input, [data-baseweb="select"] [role="combobox"]');
            selectInputs.forEach(input => {
                if (input === doc.activeElement) {
                    input.blur();
                }
            });
            
            // Method 2: Find open popovers and close them
            const popovers = doc.querySelectorAll('[data-baseweb="popover"][data-is-open="true"], [data-baseweb="popover"]:not([style*="display: none"])');
            popovers.forEach(popover => {
                // Try to find and click the backdrop or trigger close
                const backdrop = popover.closest('[data-baseweb="layer"]');
                if (backdrop) {
                    backdrop.style.display = 'none';
                }
            });
            
            // Method 3: Send ESC key to close any open dropdowns
            const escEvent = new KeyboardEvent('keydown', {
                key: 'Escape',
                keyCode: 27,
                bubbles: true,
                cancelable: true
            });
            doc.activeElement?.dispatchEvent(escEvent);
            doc.body.dispatchEvent(escEvent);
            
            // Method 4: Click outside on document body (fallback)
            const clickOutside = new MouseEvent('mousedown', {
                bubbles: true,
                cancelable: true,
                view: window.parent !== window ? window.parent : window
            });
            setTimeout(() => {
                doc.body.dispatchEvent(clickOutside);
            }, 50);
            
        } catch (e) {
            console.log('Error closing dropdowns:', e);
        }
    }
    
    // Function to setup auto-close listeners
    function setupAutoClose() {
        const doc = window.parent !== window ? window.parent.document : document;
        
        // More aggressive approach: Listen for clicks on multiselect options and immediately close
        function handleOptionClick(e) {
            const target = e.target;
            const option = target.closest('[role="option"], [data-baseweb="option"], li[role="option"]');
            
            if (option) {
                // Find the parent select input
                const selectContainer = option.closest('[data-baseweb="select"]');
                if (selectContainer) {
                    // Find the input/combobox element
                    const input = selectContainer.querySelector('input[role="combobox"], [role="combobox"]');
                    if (input) {
                        // Immediately blur to close dropdown
                        setTimeout(() => {
                            input.blur();
                            // Also trigger ESC key
                            const escEvent = new KeyboardEvent('keydown', {
                                key: 'Escape',
                                keyCode: 27,
                                bubbles: true,
                                cancelable: true
                            });
                            input.dispatchEvent(escEvent);
                            // Click outside to ensure it closes
                            doc.body.click();
                        }, 100);
                    }
                }
            }
        }
        
        // Use capture phase to catch events early
        doc.addEventListener('click', handleOptionClick, true);
        doc.addEventListener('mousedown', handleOptionClick, true);
        
        // Also listen for mouseup on options (some browsers trigger this)
        doc.addEventListener('mouseup', function(e) {
            if (e.target.closest('[role="option"], [data-baseweb="option"]')) {
                setTimeout(closeAllDropdowns, 200);
            }
        }, true);
        
        // Listen for changes in select elements using MutationObserver
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                // When attributes change on select elements
                if (mutation.type === 'attributes') {
                    const target = mutation.target;
                    // Check if it's a select element that just opened
                    if (target.hasAttribute && target.hasAttribute('data-baseweb')) {
                        // Check all selects and close any that should be closed
                        setTimeout(() => {
                            const openSelects = doc.querySelectorAll('[data-baseweb="select"] input[aria-expanded="true"]');
                            openSelects.forEach(select => {
                                // If it's not being hovered, we can try to close it
                                const popover = select.closest('[data-baseweb="select"]')?.querySelector('[data-baseweb="popover"]');
                                if (popover && !popover.matches(':hover')) {
                                    setTimeout(() => select.blur(), 300);
                                }
                            });
                        }, 500);
                    }
                }
            });
        });
        
        // Observe the entire document for changes
        observer.observe(doc.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['aria-expanded', 'data-is-open', 'style']
        });
    }
    
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupAutoClose);
    } else {
        setupAutoClose();
    }
    
    // Also setup when Streamlit reruns (iframe context)
    if (window.parent !== window) {
        const parentDoc = window.parent.document;
        if (parentDoc.readyState === 'loading') {
            parentDoc.addEventListener('DOMContentLoaded', setupAutoClose);
        } else {
            setTimeout(setupAutoClose, 500); // Delay to ensure Streamlit has rendered
        }
    }
    
    // Mobile-specific: Close sidebar when clicking outside on mobile
    function isMobile() {
        return window.innerWidth <= 768 || (window.parent !== window && window.parent.innerWidth <= 768);
    }
    
    if (isMobile()) {
        const doc = window.parent !== window ? window.parent.document : document;
        // Close sidebar when clicking on main content area
        const mainContent = doc.querySelector('.main, [data-testid="stAppViewContainer"]');
        if (mainContent) {
            mainContent.addEventListener('click', function(e) {
                const sidebar = doc.querySelector('[data-testid="stSidebar"]');
                const sidebarToggle = doc.querySelector('[data-testid="stSidebar"] button');
                if (sidebar && sidebarToggle && sidebar.getAttribute('aria-expanded') === 'true') {
                    // Don't close if clicking on sidebar itself
                    if (!e.target.closest('[data-testid="stSidebar"]')) {
                        sidebarToggle.click();
                    }
                }
            });
        }
    }
    
    // Re-run setup after Streamlit reruns (important for multiselect auto-close)
    if (window.parent !== window) {
        // Streamlit reruns cause iframe reloads, so we need to re-setup
        const observer = new MutationObserver(function() {
            setTimeout(setupAutoClose, 300);
        });
        const parentBody = window.parent.document.body;
        if (parentBody) {
            observer.observe(parentBody, {
                childList: true,
                subtree: true
            });
        }
    }
})();
</script>
""", unsafe_allow_html=True)

# Developer credit in sidebar
st.sidebar.divider()
st.sidebar.markdown(
    "<div style='text-align: center; padding: 15px 0;'>"
    "<p style='margin: 0; color: #666; font-size: 0.85em; line-height: 1.5;'>"
    "Developed by<br>"
    "<strong style='color: #1f77b4; font-size: 1.1em;'>Shivam Gulati</strong><br>"
    "<span style='font-size: 0.8em;'>Land Revenue Fellow</span>"
    "</p>"
    "<div style='margin-top: 15px; padding-top: 15px; border-top: 1px solid #e0e0e0;'>"
    "<p style='margin: 0 0 10px 0; color: #666; font-size: 0.75em; font-weight: 600; text-align: center;'>In case of Glitches</p>"
    "<div style='display: flex; flex-direction: column; gap: 8px; align-items: center; justify-content: center;'>"
    "<div style='display: flex; align-items: center; justify-content: center; gap: 8px;'>"
    "<span style='font-size: 1em;'>📧</span>"
    "<a href='mailto:Shivamgulati137@gmail.com' style='color: #1f77b4; text-decoration: none; font-size: 0.75em; word-break: break-word;'>Shivamgulati137@gmail.com</a>"
    "</div>"
    "<div style='display: flex; align-items: center; justify-content: center; gap: 8px;'>"
    "<span style='font-size: 1em;'>📱</span>"
    "<span style='color: #666; font-size: 0.75em;'>62844-12362</span>"
    "</div>"
    "</div>"
    "</div>"
    "</div>",
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

# ========== EXECUTIVE DASHBOARD ==========
st.header("📊 Brief Overview")

if latest_snapshot.empty:
    st.warning("No data available for the selected date range/filters.")
else:
    # Ensure Total is numeric before all calculations
    latest_snapshot_clean = latest_snapshot.copy()
    latest_snapshot_clean["Total"] = pd.to_numeric(latest_snapshot_clean["Total"], errors="coerce").fillna(0).astype(float)
    
    previous_snapshot_clean = previous_snapshot.copy() if not previous_snapshot.empty else pd.DataFrame()
    if not previous_snapshot_clean.empty:
        previous_snapshot_clean["Total"] = pd.to_numeric(previous_snapshot_clean["Total"], errors="coerce").fillna(0).astype(float)
    
    # Calculate key metrics - use grouped data for consistency
    snapshot_grouped = latest_snapshot_clean.groupby("Sub Division", as_index=False)["Total"].sum()
    snapshot_grouped["Total"] = pd.to_numeric(snapshot_grouped["Total"], errors="coerce").fillna(0).astype(float)
    total_latest = float(snapshot_grouped["Total"].sum())
    
    # Calculate previous total from grouped data
    if not previous_snapshot_clean.empty:
        previous_grouped = previous_snapshot_clean.groupby("Sub Division", as_index=False)["Total"].sum()
        previous_grouped["Total"] = pd.to_numeric(previous_grouped["Total"], errors="coerce").fillna(0).astype(float)
        total_previous = float(previous_grouped["Total"].sum())
    else:
        total_previous = 0.0
    
    total_change = calculate_change(total_latest, total_previous)
    
    num_subdivisions = latest_snapshot_clean["Sub Division"].nunique()
    num_officers = latest_snapshot_clean["Officer"].nunique()
    
    # Top 3 sub-divisions - sort grouped data
    snapshot_grouped = snapshot_grouped.sort_values("Total", ascending=False, ignore_index=True)
    top3_subdivisions = snapshot_grouped.head(3)
    
    # Alerts - group by Sub Division FIRST, then filter by threshold
    # This ensures we count sub-divisions based on their total pendency, not individual officer levels
    alerts_grouped = latest_snapshot_clean.groupby("Sub Division", as_index=False)["Total"].sum()
    alerts_grouped["Total"] = pd.to_numeric(alerts_grouped["Total"], errors="coerce").fillna(0).astype(float)
    alert_df = alerts_grouped[alerts_grouped["Total"] > threshold]
    num_alerts = len(alert_df) if not alert_df.empty else 0
    
    # Top pendency type - use cleaned snapshot
    pendency_columns = [
        "Uncontested Pendency", "Income Certificate", "Copying Service",
        "Inspection Records", "Overdue Mortgage", "Overdue Court Orders",
        "Overdue Fardbadars"
    ]
    available_pendency_cols = [col for col in pendency_columns if col in latest_snapshot_clean.columns]
    pendency_totals = {}
    for col in available_pendency_cols:
        # Convert to numeric and sum
        pendency_totals[col] = float(pd.to_numeric(latest_snapshot_clean[col], errors="coerce").fillna(0).sum())
    top_pendency_type = max(pendency_totals.items(), key=lambda x: x[1]) if pendency_totals else ("N/A", 0)
    
    # Key Metrics Row - Clean
    col1, col2, col3 = st.columns(3)
    
    with col1:
        delta_text = f"{total_change:+.1f}%" if previous_date else None
        delta_color = "inverse" if total_change > 0 else "normal"
        st.metric("Total Pendency", format_number(total_latest), delta=delta_text, delta_color=delta_color)
        if previous_date:
            st.caption(f"vs {previous_date.strftime('%b %d')}")
    
    with col2:
        st.metric("Sub Divisions", num_subdivisions)
    
    with col3:
        if num_alerts > 0:
            st.metric("⚠️ Alerts", num_alerts, delta="Requires attention", delta_color="inverse")
        else:
            st.metric("✅ Alerts", "0", delta="All clear")
    
    # Pendency Breakdown Section
    if available_pendency_cols and pendency_totals:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 📋 Pendency Breakdown by Type")
        
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
        if not latest_snapshot_clean.empty:
            # Sort by Total descending and take top 5 rows
            # Each row represents a unique officer-location combination
            top_officers = latest_snapshot_clean.nlargest(5, "Total")
            
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

                    # Build historical trend for this officer using the filtered dataframe df
                    officer_mask = (df["Officer"].astype(str) == str(officer)) & (df["Sub Division"].astype(str) == str(subdiv))
                    if "Tehsil/Sub Tehsil" in df.columns and pd.notna(row.get("Tehsil/Sub Tehsil", None)):
                        officer_mask = officer_mask & (df["Tehsil/Sub Tehsil"].astype(str) == str(tehsil))
                    officer_history = df[officer_mask].copy()

                    officer_trend = pd.DataFrame()
                    if not officer_history.empty and "__date" in officer_history.columns:
                        officer_trend = (
                            officer_history.groupby("__date", as_index=False)["Total"]
                            .sum()
                            .sort_values("__date")
                        )

                    col_officer, col_officer_right = st.columns([3, 2])
                    with col_officer:
                        st.markdown(
                            f"<p style='font-size: 0.95rem; font-weight: 600; color: #003366; margin: 0.25rem 0;'><strong>{subdiv}</strong> - <strong>{tehsil}</strong> - <strong>{officer}</strong></p>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            f"<p style='font-size: 1rem; color: #333; margin: 0.25rem 0;'><strong>{format_number(officer_total)}</strong> <span style='color: #666; font-size: 0.85rem;'>({pct_of_total:.1f}% of total)</span></p>",
                            unsafe_allow_html=True,
                        )
                    with col_officer_right:
                        # Show a minimalist trend chart when we have data; otherwise fall back to colored bar
                        if not officer_trend.empty and officer_trend["Total"].sum() > 0:
                            fig_officer = px.line(
                                officer_trend,
                                x="__date",
                                y="Total",
                                markers=True,
                                color_discrete_sequence=[progress_color],
                            )
                            fig_officer.update_traces(line=dict(width=2), marker=dict(size=5))
                            fig_officer.update_layout(
                                height=120,
                                margin=dict(l=10, r=10, t=10, b=10),
                                showlegend=False,
                                xaxis_title=None,
                                yaxis_title=None,
                                plot_bgcolor="rgba(0,0,0,0)",
                                paper_bgcolor="rgba(0,0,0,0)",
                            )
                            fig_officer.update_xaxes(showgrid=False, showticklabels=False)
                            fig_officer.update_yaxes(showgrid=False, showticklabels=False)
                            st.plotly_chart(fig_officer, use_container_width=True)
                        else:
                            # Custom colored progress bar (fallback when no trend data)
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
                                unsafe_allow_html=True,
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
        # alert_df is already grouped and filtered, so we can use it directly
        if not alert_df.empty:
            # Sort by Total to get the highest alert (already numeric from grouping)
            top_alert = alert_df.sort_values("Total", ascending=False, ignore_index=True).head(1)
            if not top_alert.empty:
                st.markdown(f"<p style='font-weight: 600; color: #003366; margin: 0.5rem 0;'>Highest Alert:</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='font-size: 1rem; font-weight: 600; color: #333; margin: 0.5rem 0;'>{top_alert.iloc[0]['Sub Division']}</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='font-size: 1.2rem; font-weight: 700; color: #003366; margin: 0.5rem 0;'>{format_number(int(top_alert.iloc[0]['Total']))}</p>", unsafe_allow_html=True)
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
            # Prepare data for bar chart - show all or top 10, whichever is less
            num_to_show = min(10, len(snapshot_grouped))
            chart_data = snapshot_grouped.head(num_to_show).copy()
            
            # Dynamic title based on actual number of sub-divisions
            if len(snapshot_grouped) <= 10:
                chart_title = f"All Sub Divisions ({len(chart_data)})"
            else:
                chart_title = f"Top {num_to_show} Sub Divisions"
            
            # Create a more visual bar chart
            fig_dist = px.bar(
                chart_data, 
                x="Sub Division", 
                y="Total",
                title=chart_title,
                color="Total",
                color_continuous_scale="Reds",
                text="Total"
            )
            
            # Format text labels
            fig_dist.update_traces(
                texttemplate='%{text:,}',
                textposition='outside',
                textfont=dict(size=10),
                marker_line_color='rgba(0,0,0,0.2)',
                marker_line_width=1
            )
            
            # Calculate max value for better y-axis scaling
            max_val = float(chart_data["Total"].max())
            y_max = max_val * 1.15  # Add 15% padding for text labels
            
            # Update layout with proper scaling and alignment
            fig_dist.update_layout(
                height=300,
                showlegend=False,
                xaxis_title="Sub Division",
                yaxis_title="Total Pendency",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                autosize=True,
                margin=dict(l=60, r=40, t=50, b=100),
                xaxis=dict(
                    categoryorder='total descending',
                    gridcolor='rgba(128,128,128,0.2)',
                    tickangle=45,
                    tickfont=dict(size=10),
                    title_font=dict(size=12)
                ),
                yaxis=dict(
                    gridcolor='rgba(128,128,128,0.2)',
                    range=[0, y_max],
                    tickformat=',',
                    tickfont=dict(size=10),
                    title_font=dict(size=12),
                    showgrid=True
                ),
                title=dict(
                    font=dict(size=14),
                    x=0.5,
                    xanchor='center'
                )
            )
            
            st.plotly_chart(fig_dist, use_container_width=True, config={'displayModeBar': False, 'responsive': True})
        else:
            st.info("No data available")
    
    # Heatmap: Sub Division vs Pendency Types
    if available_pendency_cols and not latest_snapshot_clean.empty:
        st.markdown("### 🔥 Heatmap: Sub Division vs Pendency Types")
        heatmap_data = []
        for subdiv in latest_snapshot_clean["Sub Division"].dropna().unique()[:15]:  # Top 15
            subdiv_df = latest_snapshot_clean[latest_snapshot_clean["Sub Division"] == subdiv]
            row = {"Sub Division": subdiv}
            for pcol in available_pendency_cols:
                # Convert to numeric before summing
                row[pcol] = float(pd.to_numeric(subdiv_df[pcol], errors="coerce").fillna(0).sum())
            heatmap_data.append(row)
        
        # Create heatmap once after collecting all data
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
                
    # Complete Summary Table
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📋 Complete Summary Table")
    
    if not latest_snapshot_clean.empty:
        # Add toggle to group by Tehsil
        has_tehsil_col = "Tehsil/Sub Tehsil" in latest_snapshot_clean.columns
        
        if has_tehsil_col:
            view_option = st.radio(
                "**Group by:**",
                ["Officer Level", "Tehsil Level"],
                horizontal=True,
                key="summary_table_view"
            )
        else:
            view_option = "Officer Level"
        
        # Create comprehensive summary table - use cleaned snapshot
        if view_option == "Tehsil Level" and has_tehsil_col:
            # Group by Tehsil and aggregate
            summary_table = latest_snapshot_clean.copy()
            
            # Group by Tehsil/Sub Tehsil and sum all numeric columns
            group_cols = ["Tehsil/Sub Tehsil"]
            agg_dict = {}
            
            # Sum all pendency columns
            for col in available_pendency_cols:
                agg_dict[col] = 'sum'
            agg_dict["Total"] = 'sum'
            
            # Group and aggregate
            summary_table = summary_table.groupby(group_cols, as_index=False).agg(agg_dict)
            
            # Ensure all numeric columns are properly typed
            for col in available_pendency_cols + ["Total"]:
                summary_table[col] = pd.to_numeric(summary_table[col], errors="coerce").fillna(0).astype(float)
            
            # Recalculate total_latest for tehsil-level view
            tehsil_total_latest = float(summary_table["Total"].sum())
            
            # Add percentage column based on tehsil-level total
            summary_table["% of Total"] = (summary_table["Total"] / tehsil_total_latest * 100).round(2) if tehsil_total_latest > 0 else 0
            
            # Add rank
            summary_table["Rank"] = summary_table["Total"].rank(ascending=False, method="dense").astype(int)
            
            # Add alert indicator
            summary_table["Alert"] = summary_table["Total"].apply(lambda x: "⚠️" if x > threshold else "✅")
            
            # Select and order columns for display (no Officer column for tehsil view)
            display_cols = []
            display_cols.append("Rank")
            display_cols.append("Tehsil/Sub Tehsil")
            
            # Add all pendency type columns
            for col in available_pendency_cols:
                display_cols.append(col)
            
            # Add summary columns
            display_cols.extend(["Total", "% of Total", "Alert"])
            
            # Create final table
            final_table = summary_table[display_cols].copy()
            
            # Sort by Total descending (before formatting)
            final_table = final_table.sort_values("Total", ascending=False).reset_index(drop=True)
            
            # Update total for display
            display_total = tehsil_total_latest
        else:
            # Officer Level view (original logic)
            summary_table = latest_snapshot_clean.copy()
            
            # Add percentage column - use total_latest from grouped data
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
            
            # Update total for display
            display_total = total_latest
        
        # Format numeric columns for display
        final_table_display = final_table.copy()
        for col in available_pendency_cols + ["Total"]:
            if col in final_table_display.columns:
                final_table_display[col] = final_table_display[col].apply(format_number)
        
        # Format percentage
        if "% of Total" in final_table_display.columns:
            final_table_display["% of Total"] = final_table_display["% of Total"].apply(lambda x: f"{x:.2f}%")
        
        # Create abbreviated column names for better fit
        column_abbreviations = {
            "Uncontested Pendency": "Uncontested",
            "Income Certificate": "Income Cert",
            "Copying Service": "Copying",
            "Inspection Records": "Inspection",
            "Overdue Mortgage": "Mortgage",
            "Overdue Court Orders": "Court Orders",
            "Overdue Fardbadars": "Fardbadars",
            "Tehsil/Sub Tehsil": "Tehsil",
            "% of Total": "%"
        }
        
        # Rename columns for display
        final_table_display_renamed = final_table_display.rename(columns=column_abbreviations)
        
        # Add summary statistics row
        view_type = "Tehsils" if view_option == "Tehsil Level" else "Records"
        st.markdown(f"**Total {view_type}:** {len(final_table_display_renamed)} | **Date:** {latest_date.strftime('%B %d, %Y') if pd.notna(latest_date) else 'Latest'}")
        
        # Add CSS for responsive table with horizontal scroll if needed
        st.markdown("""
        <style>
        /* Make table container fit viewport width */
        .stDataFrame {
            width: 100% !important;
            max-width: 100% !important;
        }
        /* Style the dataframe to be more compact */
        div[data-testid="stDataFrame"] {
            overflow-x: auto;
            overflow-y: auto;
            max-width: 100%;
        }
        /* Make table cells more compact */
        div[data-testid="stDataFrame"] table {
            font-size: 0.85rem !important;
            width: 100% !important;
            table-layout: auto !important;
        }
        /* Compact column headers */
        div[data-testid="stDataFrame"] th {
            padding: 0.5rem 0.4rem !important;
            font-size: 0.8rem !important;
            white-space: nowrap;
        }
        /* Compact table cells */
        div[data-testid="stDataFrame"] td {
            padding: 0.4rem 0.3rem !important;
            font-size: 0.8rem !important;
            white-space: nowrap;
        }
        /* Ensure numeric columns are right-aligned for better readability */
        div[data-testid="stDataFrame"] td:nth-child(n+2) {
            text-align: right;
        }
        /* Rank and Alert columns can be centered */
        div[data-testid="stDataFrame"] td:first-child,
        div[data-testid="stDataFrame"] td:last-child {
            text-align: center;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Display table with search and sort
        st.dataframe(
            final_table_display_renamed,
                width='stretch',
            hide_index=True,
            height=400,
            use_container_width=True
        )
    else:
        st.info("No data available for the summary table.")


# Footer - with developer credit
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
        "<p style='margin: 0 0 8px 0; color: #666; font-size: 0.9em;'>"
        "Developed by <strong style='color: #1f77b4;'>Shivam Gulati</strong><br>"
        "<span style='font-size: 0.85em;'>Land Revenue Fellow</span>"
        "</p>"
        "<div style='margin-top: 10px; padding-top: 10px; border-top: 1px solid #e0e0e0;'>"
        "<p style='margin: 0 0 8px 0; color: #666; font-size: 0.75em; font-weight: 600; text-align: right;'>In case of Glitches</p>"
        "<div style='display: flex; flex-direction: column; gap: 6px; align-items: flex-end; justify-content: flex-start;'>"
        "<div style='display: flex; align-items: center; justify-content: flex-end; gap: 8px;'>"
        "<span style='font-size: 0.9em;'>📧</span>"
        "<a href='mailto:Shivamgulati137@gmail.com' style='color: #1f77b4; text-decoration: none; font-size: 0.75em; word-break: break-word;'>Shivamgulati137@gmail.com</a>"
        "</div>"
        "<div style='display: flex; align-items: center; justify-content: flex-end; gap: 8px;'>"
        "<span style='font-size: 0.9em;'>📱</span>"
        "<span style='color: #666; font-size: 0.75em;'>62844-12362</span>"
        "</div>"
        "</div>"
        "</div>"
        "</div>",
        unsafe_allow_html=True
    )