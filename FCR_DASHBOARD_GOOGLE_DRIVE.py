# FCR Dashboard with Google Drive Integration
"""
Streamlit FCR Dashboard with Google Drive Integration
Reads Excel files from Google Drive and shows:
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

# Core function to load and process Excel files from Google Drive or local
def _load_all_files_core() -> pd.DataFrame:
    """Load all Excel files from Google Drive or local folder and process them."""
    files_data = []
    failed_files = []
    
    try:
        if use_google_drive and storage:
            # Load from Google Drive
            logger.info("Loading files from Google Drive...")
            drive_files = storage.list_files()
            
            if not drive_files:
                logger.info("No Excel files found in Google Drive folder")
                return pd.DataFrame()
            
            for file_info in drive_files:
                filename = file_info['name']
                file_id = file_info['id']
                
                if filename.startswith("~$"):
                    continue
                
                try:
                    # Download file from Google Drive
                    file_data = storage.download_file(file_id)
                    if not file_data.getvalue():
                        logger.warning(f"File {filename} is empty, skipping")
                        failed_files.append((filename, "Empty file"))
                        continue
                    
                    # Read Excel file from bytes
                    try:
                        df = pd.read_excel(file_data, engine="openpyxl")
                    except Exception as e:
                        logger.warning(f"Failed to read {filename} with default sheet, trying first sheet: {e}")
                        file_data.seek(0)
                        df = pd.read_excel(file_data, sheet_name=0, engine="openpyxl")
                    
                    if df.empty:
                        logger.warning(f"File {filename} is empty, skipping")
                        failed_files.append((filename, "Empty file"))
                        continue
                    
                    files_data.append((df, filename))
                    
                except Exception as e:
                    logger.error(f"Error processing file {filename}: {str(e)}")
                    failed_files.append((filename, str(e)))
                    continue
        
        else:
            # Load from local folder (fallback)
            logger.info("Loading files from local folder...")
            folder = Path(DATA_FOLDER)
            if not folder.exists():
                logger.warning(f"Data folder does not exist: {folder}")
                return pd.DataFrame()
            
            local_files = sorted(folder.glob("*.xlsx"))
            if not local_files:
                logger.info(f"No Excel files found in {folder}")
                return pd.DataFrame()
            
            for f in local_files:
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
                    
                    files_data.append((df, f.name))
                    
                except Exception as e:
                    logger.error(f"Error processing file {f.name}: {str(e)}")
                    failed_files.append((f.name, str(e)))
                    continue
        
        if not files_data:
            if failed_files:
                logger.error(f"All files failed to load. Failed: {failed_files}")
            return pd.DataFrame()
        
        # Process all dataframes
        rows = []
        for df, filename in files_data:
            try:
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
                is_valid, error_msg = validate_dataframe(df, filename)
                if not is_valid:
                    logger.warning(f"Validation failed for {filename}: {error_msg}")
                    failed_files.append((filename, error_msg))
                    continue
                
                # Parse date from filename
                m = FILENAME_DATE_RE.search(filename)
                file_date = pd.to_datetime(m.group(1), format=DATE_FORMAT) if m else pd.NaT
                if pd.isna(file_date):
                    logger.warning(f"Could not parse date from filename: {filename}")
                
                df["__source_file"] = filename
                df["__date"] = file_date
                rows.append(df)
                
            except Exception as e:
                logger.error(f"Error processing {filename}: {str(e)}")
                failed_files.append((filename, str(e)))
                continue
        
        if not rows:
            if failed_files:
                logger.error(f"All files failed to process. Failed: {failed_files}")
            return pd.DataFrame()
        
        # Combine all dataframes
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
        
        # Calculate Total if it doesn't exist
        if "Total" not in combined.columns:
            available_pendency_cols = [col for col in pendency_columns if col in combined.columns]
            if available_pendency_cols:
                combined["Total"] = combined[available_pendency_cols].sum(axis=1)
            else:
                combined["Total"] = 0
        else:
            combined["Total"] = pd.to_numeric(combined["Total"], errors="coerce").fillna(0).astype(int)
        
        # Ensure Sub Division column
        if "Sub Division" not in combined.columns and "SubDivision" in combined.columns:
            combined.rename(columns={"SubDivision": "Sub Division"}, inplace=True)
        
        # Standardize Rank
        if "Rank" in combined.columns:
            combined["Rank"] = pd.to_numeric(combined["Rank"], errors="coerce")
        
        # Fill missing useful columns
        for col in ["Officer", "Sub Division"]:
            if col not in combined.columns:
                combined[col] = "Unknown"
        
        if failed_files:
            logger.warning(f"Some files failed to load: {failed_files}")
        
        return combined
        
    except Exception as e:
        logger.error(f"Error loading files: {e}")
        return pd.DataFrame()

# Non-cached version for when we need fresh data
def _load_all_files_uncached() -> pd.DataFrame:
    """Load files without caching - used for refresh"""
    return _load_all_files_core()

# Cached version for normal operation
@st.cache_data(ttl=300, show_spinner="Loading data files...")
def load_all_files(cache_version: str = "v1") -> pd.DataFrame:
    """Load all Excel files from Google Drive or local folder."""
    return _load_all_files_core()

# Include all the CSS styling from the original file
# (Copy the entire CSS section from FCR_DASHBOARD.py - lines 237-624)

