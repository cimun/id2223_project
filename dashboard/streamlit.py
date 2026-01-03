import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone, time
import hopsworks
import plotly.graph_objects as go

# =====================================================================
# 0. CONFIG & MAPPING
# =====================================================================
HOPSWORKS_PROJECT = "chris"
HOPSWORKS_API_KEY = "uyF3wIn3OVAm1Sne.y9dXwMhnPr9JHLdVpfkfwCEBy8JJjq7c4j9IOsbLcKwBfnDtnxWvb5PNwa5E3cxT"
FEATURE_GROUP_VERSION = 1
TIME_COL = "timestamp"
PREDICTED_VALUE_COL = "predicted_energy"

AREAS = {
    "Sweden SE4": {"lat": 56.4570, "lon": 14.2246, "suffix": "se_4"},
    "Sweden SE3": {"lat": 59.4484, "lon": 15.3615, "suffix": "se_3"},
    "Sweden SE2": {"lat": 63.4170, "lon": 16.0875, "suffix": "se_2"},
    "Sweden SE1": {"lat": 66.8319, "lon": 21.0965, "suffix": "se_1"},
}

def get_fg_names(area_name, energy_type):
    suffix = AREAS[area_name]["suffix"]
    pred_fg = f"{energy_type.lower()}_energy_predictions_{suffix}"
    real_fg = f"energy_production_{suffix}"
    real_col = energy_type.lower() 
    return pred_fg, real_fg, real_col

# =====================================================================
# 1. SESSION STATE INITIALIZATION
# =====================================================================
# This is the "Source of Truth" for our two-way sync
if 'selected_area' not in st.session_state:
    st.session_state.selected_area = "Sweden SE4"

# =====================================================================
# 2. PAGE SETUP & CONNECTORS
# =====================================================================
st.set_page_config(page_title="Energy Transparency Platform", layout="wide")

st.title("Energy Forecast Dashboard")

st.markdown(
    """
    """
)

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
# 3. UI - MAP & CONTROLS (THE SYNC PART)
# =====================================================================
map_col, ctrl_col = st.columns([2, 1])

with map_col:
    st.markdown("Select Region")
    
    # Highlight the selected area on the map by changing color
    colors = ['#ff7f0e' if a == st.session_state.selected_area else '#003366' for a in AREAS.keys()]
    
    map_fig = go.Figure(go.Scattermapbox(
        lat=[AREAS[a]["lat"] for a in AREAS],
        lon=[AREAS[a]["lon"] for a in AREAS],
        mode='markers+text',
        marker=go.scattermapbox.Marker(size=20, color=colors),
        text=list(AREAS.keys()),
        textposition="top center",
        hoverinfo='text'
    ))

    map_fig.update_layout(
        mapbox=dict(style="carto-positron", zoom=2.8, center={"lat": 61, "lon": 17}),
        margin={"r":0,"t":0,"l":0,"b":0}, height=400, clickmode='event+select'
    )

    map_selection = st.plotly_chart(map_fig, use_container_width=True, on_select="rerun")

    # SYNC 1: Map -> State
    if map_selection and map_selection.get("selection", {}).get("points"):
        clicked_area = map_selection["selection"]["points"][0]["text"]
        if clicked_area != st.session_state.selected_area:
            st.session_state.selected_area = clicked_area
            st.rerun()

with ctrl_col:
    st.markdown("Filters")
    energy_type = st.radio("Production Type", ["Solar", "Wind"])

    area_list = list(AREAS.keys())
    
    # We use 'selected_area' as the source of truth.
    # We do NOT give the selectbox its own separate key to avoid conflicts.
    current_index = area_list.index(st.session_state.selected_area)
    
    selected_area = st.selectbox(
        "Area", 
        area_list, 
        index=current_index,
        # Removing the 'key' here allows the 'index' to force the text update
    )

    # If the user manually changes the dropdown, update the state and rerun
    if selected_area != st.session_state.selected_area:
        st.session_state.selected_area = selected_area
        st.rerun()

    st.write("---")
    st.success(f"🟢 Connected: {HOPSWORKS_PROJECT}")

# =====================================================================
# 4. DATA LOADING & FILTERING
# =====================================================================
# Always use st.session_state.selected_area for the logic
pred_fg, real_fg, real_col = get_fg_names(st.session_state.selected_area, energy_type)

try:
    df_pred = load_data(pred_fg)
    df_real = load_data(real_fg)
    
    global_min = min(df_pred[TIME_COL].min(), df_real[TIME_COL].min()).to_pydatetime()
    global_max = max(df_pred[TIME_COL].max(), df_real[TIME_COL].max()).to_pydatetime()
except Exception as e:
    st.error(f"Data missing for {st.session_state.selected_area}")
    st.stop()

# --- Synced Time & Date Selectors ---
st.markdown("---")
if "actual_range" not in st.session_state:
    st.session_state.actual_range = (global_min, global_max)

d_col1, d_col2 = st.columns(2)
with d_col1:
    new_start_date = st.date_input("Start Date", value=st.session_state.actual_range[0].date())
with d_col2:
    new_end_date = st.date_input("End Date", value=st.session_state.actual_range[1].date())

new_range = st.slider("Time Range", min_value=global_min, max_value=global_max, 
                       value=st.session_state.actual_range, format="MMM DD, HH:mm")

# Logic for Time Sync
if new_start_date != st.session_state.actual_range[0].date() or new_end_date != st.session_state.actual_range[1].date():
    start_dt = datetime.combine(new_start_date, time.min).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(new_end_date, time.max).replace(tzinfo=timezone.utc)
    st.session_state.actual_range = (start_dt, end_dt)
    st.rerun()
else:
    st.session_state.actual_range = new_range

actual_start, actual_end = st.session_state.actual_range

# Filter and Plot
p_plot = df_pred[(df_pred[TIME_COL] >= actual_start) & (df_pred[TIME_COL] <= actual_end)]
r_plot = df_real[(df_real[TIME_COL] >= actual_start) & (df_real[TIME_COL] <= actual_end)]

# =====================================================================
# 5. CHARTING
# =====================================================================
fig = go.Figure()
fig.add_trace(go.Scatter(x=p_plot[TIME_COL], y=p_plot[PREDICTED_VALUE_COL], 
                         name="Forecast", line=dict(color='#003366', width=2, dash='dash')))
fig.add_trace(go.Scatter(x=r_plot[TIME_COL], y=r_plot[real_col], 
                         name="Actual", fill='tozeroy', line=dict(color='#ff7f0e', width=2)))

fig.update_layout(title=f"{energy_type} in {st.session_state.selected_area}", 
                  hovermode="x unified", template="plotly_white", height=500)
st.plotly_chart(fig, use_container_width=True)



# =====================================================================
# 6. RAW DATA PREVIEW
# =====================================================================
with st.expander("View Detailed Data Log"):
    # Combine predictions and real data for the table view
    # We rename columns slightly so it's clear in the table which is which
    table_p = p_plot[[TIME_COL, PREDICTED_VALUE_COL]].copy().rename(columns={PREDICTED_VALUE_COL: "Forecasted MW"})
    table_r = r_plot[[TIME_COL, real_col]].copy().rename(columns={real_col: "Actual MW"})
    
    # Merge on timestamp to see them side-by-side
    merged_df = pd.merge(table_p, table_r, on=TIME_COL, how="outer").sort_values(by=TIME_COL, ascending=False)
    
    st.write(f"Showing raw data for **{st.session_state.selected_area}** ({energy_type})")
    st.dataframe(
        merged_df.style.format({
            "Forecasted MW": "{:.2f}",
            "Actual MW": "{:.2f}"
        }), 
        use_container_width=True
    )

st.caption(
    f"Data window: **{actual_start.strftime('%Y-%m-%d %H:%M')}** to **{actual_end.strftime('%Y-%m-%d %H:%M')}** (UTC)"
)