import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import hopsworks
import plotly.graph_objects as go
import time

# =====================================================================
# 0. CONFIG & MAPPING (Mimicking ENTSO-E Areas)
# =====================================================================

HOPSWORKS_PROJECT = "chris"
HOPSWORKS_API_KEY = "uyF3wIn3OVAm1Sne.y9dXwMhnPr9JHLdVpfkfwCEBy8JJjq7c4j9IOsbLcKwBfnDtnxWvb5PNwa5E3cxT"
FEATURE_GROUP_VERSION = 1
TIME_COL = "timestamp"
PREDICTED_VALUE_COL = "predicted_energy"

# Define your areas with their coordinates and naming suffixes
AREAS = {
    "Sweden SE4": {"lat": 56.45704350532567, "lon": 14.224629482085703, "suffix": "se_4"},
    "Sweden SE3": {"lat": 59.44841932603451, "lon": 15.36155412007809, "suffix": "se_3"},
    "Sweden SE2": {"lat": 63.41704926197734, "lon": 16.087507002857887, "suffix": "se_2"},
    "Sweden SE1": {"lat": 66.83197545465562, "lon": 21.09658182376257, "suffix": "se_1"},

}

# Mapping logic to match your FG naming: "energy_predictions_area"
def get_fg_names(area_name, energy_type):
    suffix = AREAS[area_name]["suffix"]
    pred_fg = f"{energy_type.lower()}_energy_predictions_{suffix}"
    # Map to real data FG and the specific column name
    real_fg = f"energy_production_{suffix}"
    real_col = energy_type.lower() 
    return pred_fg, real_fg, real_col

# =====================================================================
# 1. PAGE SETUP
# =====================================================================
st.set_page_config(page_title="Energy Transparency Platform", layout="wide")

# Custom CSS for ENTSO-E look
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 10px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

st.title("⚡ Total Generation Forecast - Day Ahead")

# =====================================================================
# 2. HOPSWORKS CONNECTORS (UNCHANGED)
# =====================================================================
@st.cache_resource(show_spinner="Connecting to Hopsworks...")
def connect_hopsworks():
    project = hopsworks.login(project=HOPSWORKS_PROJECT, api_key_value=HOPSWORKS_API_KEY)
    return project.get_feature_store()

@st.cache_data(show_spinner="Syncing data...")
def load_data(fg_name: str):
    fg = fs.get_feature_group(fg_name, version=FEATURE_GROUP_VERSION)
    df = fg.read()
    df[TIME_COL] = pd.to_datetime(df[TIME_COL])
    return df.sort_values(by=TIME_COL).drop_duplicates(subset=[TIME_COL], keep='last')

try:
    fs = connect_hopsworks()
except Exception as e:
    st.error(f"Connection Failed: {e}")
    st.stop()


# =====================================================================
# 3 & 4. ACTION BAR & MAP SELECTOR (Side-by-Side)
# =====================================================================

# Define two columns with the requested 2:1 ratio
map_col, ctrl_col = st.columns([2, 1])

with map_col:
    st.markdown("### 🗺️ Select Region")
    
    # Create the map figure
    map_fig = go.Figure(go.Scattermapbox(
        lat=[AREAS[a]["lat"] for a in AREAS],
        lon=[AREAS[a]["lon"] for a in AREAS],
        mode='markers+text',
        marker=go.scattermapbox.Marker(size=18, color='#003366'),
        text=list(AREAS.keys()),
        textposition="top center",
        hoverinfo='text'
    ))

    map_fig.update_layout(
        mapbox=dict(
            style="carto-positron", 
            zoom=3.8, 
            center={"lat": 58, "lon": 15}
        ),
        margin={"r":0,"t":0,"l":0,"b":0},
        height=400,
        clickmode='event+select'
    )

    # Render map and capture interaction
    map_selection = st.plotly_chart(map_fig, use_container_width=True, on_select="rerun")

    # Sync Map Click to Session State
    if map_selection and map_selection.get("selection", {}).get("points"):
        new_area = map_selection["selection"]["points"][0]["text"]
        if new_area != st.session_state.get('selected_area'):
            st.session_state.selected_area = new_area
            st.rerun()

with ctrl_col:
    st.markdown("### ⚙️ Filters")
    
    # Selection logic
    energy_type = st.radio("Production Type", ["Solar", "Wind"], horizontal=False)
    
    # Use session_state to keep dropdown synced with map
    selected_area = st.selectbox(
        "Bidding Zone", 
        list(AREAS.keys()), 
        index=list(AREAS.keys()).index(st.session_state.get('selected_area', "Sweden SE4")),
        key="area_select_dropdown"
    )
    
    # Update state if dropdown changes
    if selected_area != st.session_state.get('selected_area'):
        st.session_state.selected_area = selected_area

    # Add mini metrics for context (Standard ENTSO-E style)
    st.write("---")
    st.caption("Connection Status")
    st.success(f"🟢 **{HOPSWORKS_PROJECT}**")


# =====================================================================
# 3. ACTION BAR (Mimicking the Site UI)
# =====================================================================
# State management for Map-to-Dropdown sync

# if 'selected_area' not in st.session_state:
#     st.session_state.selected_area = list(AREAS.keys())[0]

# # Row: Filter Controls
# col1, col2, col3 = st.columns([2, 2, 1])
# with col1:
#     energy_type = st.selectbox("Production Type", ["Solar", "Wind"])
# with col2:
#     selected_area = st.selectbox("Bidding Zone / Area", list(AREAS.keys()), key="area_select")
# with col3:
#     st.write("") # Spacer
#     st.success(f"Connected: {HOPSWORKS_PROJECT}")

# # =====================================================================
# # 4. AREA SELECTOR MAP
# # =====================================================================
# map_fig = go.Figure(go.Scattermapbox(
#     lat=[AREAS[a]["lat"] for a in AREAS],
#     lon=[AREAS[a]["lon"] for a in AREAS],
#     mode='markers+text',
#     marker=go.scattermapbox.Marker(size=15, color='#003366'),
#     text=list(AREAS.keys()),
#     hoverinfo='text'
# ))

# map_fig.update_layout(
#     mapbox=dict(style="carto-positron", zoom=4, center={"lat": 58, "lon": 15}),
#     margin={"r":0,"t":0,"l":0,"b":0}, height=250, clickmode='event+select'
# )

# # Render map and capture interaction
# map_selection = st.plotly_chart(map_fig, use_container_width=True, on_select="rerun")

# # If map is clicked, update the selectbox area
# if map_selection and map_selection.get("selection", {}).get("points"):
#     new_area = map_selection["selection"]["points"][0]["text"]
#     if new_area != selected_area:
#         st.session_state.area_select = new_area
#         st.rerun()

# =====================================================================
# 5. DATA LOADING & PROCESSING
# =====================================================================
pred_fg, real_fg, real_col = get_fg_names(selected_area, energy_type)

try:
    df_pred = load_data(pred_fg)
    df_real = load_data(real_fg)
    
    # Calculate Global Bounds
    global_min = min(df_pred[TIME_COL].min(), df_real[TIME_COL].min()).to_pydatetime()
    global_max = max(df_pred[TIME_COL].max(), df_real[TIME_COL].max()).to_pydatetime()
except Exception as e:
    st.error(f"Feature Groups not found for {selected_area} {energy_type}.")
    st.stop()

# Time Slider
# st.markdown("---")
# time_range = st.slider("Time Range", min_value=global_min, max_value=global_max, 
#                        value=(global_min, global_max), format="MMM DD, HH:mm")

# # Date Selector Dropdown
# col1, col2 = st.columns(2)
# with col1:
#     start_date = st.date_input("Start Date", value=time_range[0].date())
# with col2:
#     end_date = st.date_input("End Date", value=time_range[1].date())

# # Convert date inputs to datetime at midnight
# from datetime import datetime as dt_class
# start_datetime = dt_class.combine(start_date, dt_class.min.time()).replace(tzinfo=timezone.utc)
# end_datetime = dt_class.combine(end_date, dt_class.max.time()).replace(tzinfo=timezone.utc)

# # Use date picker if it differs from slider, otherwise use slider
# if start_date != time_range[0].date() or end_date != time_range[1].date():
#     actual_start = start_datetime
#     actual_end = end_datetime
# else:
#     actual_start = time_range[0]
#     actual_end = time_range[1]

# =====================================================================
# 5.5 SYNCED TIME & DATE SELECTORS
# =====================================================================
st.markdown("---")

# Initialize session state for the range if not present
if "actual_range" not in st.session_state:
    st.session_state.actual_range = (global_min, global_max)

# 1. Date Inputs (Top Row)
d_col1, d_col2 = st.columns(2)
with d_col1:
    new_start_date = st.date_input("Start Date", value=st.session_state.actual_range[0].date())
with d_col2:
    new_end_date = st.date_input("End Date", value=st.session_state.actual_range[1].date())

# 2. Time Slider (Bottom Row)
new_range = st.slider(
    "Fine-tune Time",
    min_value=global_min,
    max_value=global_max,
    value=st.session_state.actual_range,
    format="MMM DD, HH:mm"
)

# 3. Synchronization Logic
# If the dates changed via the date_input, update the range
current_start, current_end = st.session_state.actual_range
if new_start_date != current_start.date() or new_end_date != current_end.date():
    start_dt = datetime.combine(new_start_date, time.min).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(new_end_date, time.max).replace(tzinfo=timezone.utc)
    st.session_state.actual_range = (start_dt, end_dt)
    st.rerun()
else:
    # Otherwise, update from the slider
    st.session_state.actual_range = new_range

actual_start, actual_end = st.session_state.actual_range

# Filter data
mask_p = (df_pred[TIME_COL] >= actual_start) & (df_pred[TIME_COL] <= actual_end)
mask_r = (df_real[TIME_COL] >= actual_start) & (df_real[TIME_COL] <= actual_end)
p_plot = df_pred[mask_p]
r_plot = df_real[mask_r]

# =====================================================================
# 6. ENTSO-E STYLE CHART
# =====================================================================
fig = go.Figure()

# Prediction Trace (Dashed Line)
fig.add_trace(go.Scatter(
    x=p_plot[TIME_COL], y=p_plot[PREDICTED_VALUE_COL],
    name="Day-Ahead Forecast", line=dict(color='#003366', width=2, dash='dash')
))

# Real Data Trace (Solid Area)
fig.add_trace(go.Scatter(
    x=r_plot[TIME_COL], y=r_plot[real_col],
    name="Actual Generation", fill='tozeroy',
    line=dict(color='#ff7f0e', width=2)
))

fig.update_layout(
    title=f"{energy_type} Generation in {selected_area}",
    xaxis_title="Time (UTC)", yaxis_title="MW / Energy Units",
    hovermode="x unified", template="plotly_white", height=500
)

st.plotly_chart(fig, use_container_width=True)

# Data Table
with st.expander("View Detailed Data Log"):
    st.dataframe(p_plot.tail(20))