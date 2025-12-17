import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import os
import hopsworks

# =====================================================================
# 0. HARD-CODED CONFIG  (EDIT THESE ONLY)
# =====================================================================

HOPSWORKS_PROJECT = "cimun"
HOPSWORKS_API_KEY = "uyF3wIn3OVAm1Sne.y9dXwMhnPr9JHLdVpfkfwCEBy8JJjq7c4j9IOsbLcKwBfnDtnxWvb5PNwa5E3cxT"

# List of prediction feature groups to visualize
PREDICTION_FEATURE_GROUPS = [
    "aq_predictions_drosserweg",
    "aq_predictions_johannes_filzer_strasse",
    "aq_predictions_marie_andessner_platz",
    "aq_predictions_hallwang"
]

FEATURE_GROUP_VERSION = 1

# Mandatory column names inside each prediction FG
TIME_COL = "date"
VALUE_COL = "predicted_pm25"

# =====================================================================
# 1. STREAMLIT PAGE CONFIG
# =====================================================================

st.set_page_config(
    page_title="Energy Forecast Dashboard",
    layout="wide"
)

st.title("🔋 Energy Forecast Dashboard")

st.markdown(
    """
    Forecasts loaded directly from **Hopsworks**, using hard-coded project and API key.  
    Select any prediction feature group from the list and browse forward 7 days or more.
    """
)

# =====================================================================
# 2. HOPSWORKS CONNECTION (HARDCODED)
# =====================================================================

@st.cache_resource(show_spinner="Connecting to Hopsworks...")
def connect_hopsworks():
    import hopsworks
    print("Logging in...")
    project = hopsworks.login(
        project=HOPSWORKS_PROJECT,
        api_key_value=HOPSWORKS_API_KEY
    )
    print("Getting feature store...")
    fs = project.get_feature_store()
    return fs

try:
    fs = connect_hopsworks()
    st.success(f"Connected to Hopsworks project: **{HOPSWORKS_PROJECT}**")
except Exception as e:
    st.error(f"❌ Failed to connect to Hopsworks: {e}")
    st.stop()

# =====================================================================
# 3. READ FEATURE GROUPS
# =====================================================================

@st.cache_data(show_spinner="Loading feature group...")
def load_feature_group(fg_name: str, version: int):
    fg = fs.get_feature_group(fg_name, version=version)
    df = fg.read()
    df[TIME_COL] = pd.to_datetime(df[TIME_COL])
    return df


# =====================================================================
# 4. UI – SELECT PREDICTION SETS
# =====================================================================

st.subheader("Select Predictions")

selected_fgs = st.multiselect(
    "Feature groups",
    PREDICTION_FEATURE_GROUPS,
    default=[PREDICTION_FEATURE_GROUPS[0]],
    help="Overlay multiple prediction datasets on the same plot."
)

if not selected_fgs:
    st.warning("Please select at least one feature group.")
    st.stop()

# =====================================================================
# 5. LOAD ALL SELECTED FEATURE GROUPS
# =====================================================================

loaded = {}
global_min, global_max = None, None

for fg_name in selected_fgs:
    try:
        df = load_feature_group(fg_name, FEATURE_GROUP_VERSION)
        loaded[fg_name] = df

        fg_min = df[TIME_COL].min().to_pydatetime()
        fg_max = df[TIME_COL].max().to_pydatetime()
    
        global_min = fg_min if global_min is None else min(global_min, fg_min)
        global_max = fg_max if global_max is None else max(global_max, fg_max)

    except Exception as e:
        st.error(f"Failed to read FG '{fg_name}': {e}")

if not loaded:
    st.error("No valid feature groups could be loaded.")
    st.stop()

# =====================================================================
# 6. TIME SLIDER (DEFAULT = NOW → NOW + 7 DAYS)
# =====================================================================

st.subheader("Time Window")

now = datetime.now(timezone.utc)
default_start = now
default_end = now + timedelta(days=7)

# clamp within available data range
default_start = max(default_start, global_min)
default_end = min(default_end, global_max)

time_range = st.slider(
    "Select time window",
    min_value=global_min,
    max_value=global_max,
    value=(default_start, default_end),
    format="YYYY-MM-DD HH:mm"
)

start_time, end_time = time_range

# =====================================================================
# 7. PREPARE PLOT DATA
# =====================================================================

combined = None

for fg_name, df in loaded.items():
    mask = (df[TIME_COL] >= start_time) & (df[TIME_COL] <= end_time)
    tmp = df.loc[mask, [TIME_COL, VALUE_COL]].copy()
    tmp = tmp.rename(columns={TIME_COL: "time", VALUE_COL: fg_name})
    tmp = tmp.set_index("time").sort_index()

    combined = tmp if combined is None else combined.join(tmp, how="outer")

# =====================================================================
# 8. PLOT
# =====================================================================

st.subheader("Forecast Visualization")

if combined is None or combined.empty:
    st.warning("No data in the selected window.")
else:
    combined = combined.sort_index()
    st.line_chart(combined)

    with st.expander("Preview Raw Data"):
        st.dataframe(combined.reset_index().head(200))

st.caption(
    f"Showing window: **{start_time.strftime('%Y-%m-%d %H:%M')} → {end_time.strftime('%Y-%m-%d %H:%M')} (UTC)**"
)
