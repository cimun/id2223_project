import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import os
import hopsworks
import plotly.graph_objects as go

# =====================================================================
# 0. HARD-CODED CONFIG  (EDIT THESE ONLY)
# =====================================================================

HOPSWORKS_PROJECT = "chris"
HOPSWORKS_API_KEY = "uyF3wIn3OVAm1Sne.y9dXwMhnPr9JHLdVpfkfwCEBy8JJjq7c4j9IOsbLcKwBfnDtnxWvb5PNwa5E3cxT"

# List of prediction feature groups to visualize
PREDICTION_FEATURE_GROUPS = [
    "solar_energy_predictions_se_4",
    "wind_energy_predictions_se_4"
]

# List of real data feature groups with their corresponding value columns
# Format: (feature_group_name, value_column_name)
REAL_DATA_FEATURE_GROUPS = [
    ("energy_production_se_4", "solar"),
    ("energy_production_se_4", "wind")
]

FEATURE_GROUP_VERSION = 1

# Mandatory column names inside each prediction FG
TIME_COL = "timestamp"
PREDICTED_VALUE_COL = "predicted_energy"

# =====================================================================
# 1. STREAMLIT PAGE CONFIG
# =====================================================================

st.set_page_config(
    page_title="Energy Forecast Dashboard",
    layout="wide"
)

st.title("Energy Forecast Dashboard")

st.markdown(
    """
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

    df = df.sort_values(by=[TIME_COL]) # Ensure order
    df = df.drop_duplicates(subset=[TIME_COL], keep='last')

    return df


# =====================================================================
# 4. UI – SELECT PREDICTION SETS
# =====================================================================

#st.subheader("Select Predictions")

selected_fgs = st.multiselect(
    "Sensors",
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

loaded_predictions = {}
loaded_real_data = {}
global_min, global_max = None, None

for i, fg_name in enumerate(selected_fgs):
    # Load predictions
    try:
        df = load_feature_group(fg_name, FEATURE_GROUP_VERSION)
        loaded_predictions[fg_name] = df

        fg_min = df[TIME_COL].min().to_pydatetime()
        fg_max = df[TIME_COL].max().to_pydatetime()
    
        global_min = fg_min if global_min is None else min(global_min, fg_min)
        global_max = fg_max if global_max is None else max(global_max, fg_max)

    except Exception as e:
        st.error(f"Failed to read predictions FG '{fg_name}': {e}")
    
    # Load corresponding real data
    if i < len(REAL_DATA_FEATURE_GROUPS):
        real_data_fg, real_value_col = REAL_DATA_FEATURE_GROUPS[i]
        try:
            df_real = load_feature_group(real_data_fg, FEATURE_GROUP_VERSION)
            loaded_real_data[fg_name] = (df_real, real_value_col)

            fg_min = df_real[TIME_COL].min().to_pydatetime()
            fg_max = df_real[TIME_COL].max().to_pydatetime()
        
            global_min = fg_min if global_min is None else min(global_min, fg_min)
            global_max = fg_max if global_max is None else max(global_max, fg_max)

        except Exception as e:
            st.warning(f"Could not load real data FG '{real_data_fg}': {e}")

if not loaded_predictions:
    st.error("No valid feature groups could be loaded.")
    st.stop()


# =====================================================================
# 6. TIME SLIDER (WITH SAFETY BOUNDS)
# =====================================================================

#st.subheader("Time Window")

# 1. Define the absolute bounds from your data
#slider_min = datetime(2023, 1, 1, tzinfo=timezone.utc)
slider_min = global_min
slider_max = global_max

# 2. Initialize the selection in session_state if it doesn't exist
if "current_range" not in st.session_state:
    now = datetime.now(timezone.utc)
    
    # SAFETY CHECK: 
    # If 'now' is already past the end of our data, 
    # start the slider at the end of the data minus 7 days.
    if now > slider_max:
        init_end = slider_max
        init_start = max(slider_min, slider_max - timedelta(days=7))
    else:
        init_start = max(now, slider_min)
        init_end = min(now + timedelta(days=7), slider_max)
        
    st.session_state.current_range = (init_start, init_end)

# 3. Double-check session_state isn't out of bounds (prevents crashes if data changes)
current_val = list(st.session_state.current_range)
current_val[0] = max(slider_min, min(current_val[0], slider_max))
current_val[1] = max(slider_min, min(current_val[1], slider_max))
st.session_state.current_range = tuple(current_val)

# 4. Create the slider
time_range = st.slider(
    "Select time window",
    min_value=slider_min,
    max_value=slider_max,
    key="current_range",
    format="YYYY-MM-DD HH:mm"
)

start_time, end_time = time_range

# =====================================================================
# 7. PREPARE PLOT DATA
# =====================================================================

combined_pred = None
combined_real = None

# Combine predictions
for fg_name, df in loaded_predictions.items():
    mask = (df[TIME_COL] >= start_time) & (df[TIME_COL] <= end_time)
    tmp = df.loc[mask, [TIME_COL, PREDICTED_VALUE_COL]].copy()
    tmp = tmp.rename(columns={TIME_COL: "time", PREDICTED_VALUE_COL: fg_name})
    tmp = tmp.set_index("time").sort_index()

    combined_pred = tmp if combined_pred is None else combined_pred.join(tmp, how="outer")

# Combine real data
for fg_name, (df, real_value_col) in loaded_real_data.items():
    mask = (df[TIME_COL] >= start_time) & (df[TIME_COL] <= end_time)
    tmp = df.loc[mask, [TIME_COL, real_value_col]].copy()
    tmp = tmp.rename(columns={TIME_COL: "time", real_value_col: fg_name + "_real"})
    tmp = tmp.set_index("time").sort_index()

    combined_real = tmp if combined_real is None else combined_real.join(tmp, how="outer")

# =====================================================================
# 8. PLOT
# =====================================================================

st.subheader("Forecast Visualization")

if combined_pred is None or combined_pred.empty:
    st.warning("No data in the selected window.")
else:
    combined_pred = combined_pred.sort_index()
    
    # Create Plotly figure with color palette
    fig = go.Figure()
    colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',  # Standard colors
        '#9467bd', '#8c564b', '#e377c2', '#7f7f7f'
    ]
    
    # For each sensor, create a combined trace with real and forecast data
    for idx, col in enumerate(combined_pred.columns):
        sensor_name = col
        color = colors[idx % len(colors)]  # Cycle through colors
        
        # Get prediction data
        pred_data = combined_pred[col]
        
        # Get corresponding real data if available
        real_col = col + "_real"
        real_data = combined_real[real_col] if combined_real is not None and real_col in combined_real.columns else pd.Series()
        
        if not real_data.empty:
            # Merge real and prediction data, preferring real where available
            merged = pd.DataFrame({
                'real': real_data,
                'pred': pred_data
            })
            
            # Create combined series: use real data where available, forecast elsewhere
            merged['combined'] = merged['real'].fillna(merged['pred'])
            combined_data = merged['combined']
            
            # Find the transition point from real to forecast
            last_real_idx = merged['real'].last_valid_index()
            
            if last_real_idx is not None:
                # Split into real (solid) and forecast (dashed) parts
                real_mask = merged.index <= last_real_idx
                forecast_mask = merged.index >= last_real_idx
                
                # Add real data segment (solid line)
                real_segment = combined_data[real_mask]
                if not real_segment.empty:
                    fig.add_trace(go.Scatter(
                        x=real_segment.index,
                        y=real_segment.values,
                        mode='lines',
                        name=sensor_name,
                        line=dict(color=color, dash='solid', width=2),
                        legendgroup=sensor_name,
                        showlegend=True
                    ))
                
                # Add forecast data segment (dashed line)
                forecast_segment = combined_data[forecast_mask]
                if not forecast_segment.empty:
                    fig.add_trace(go.Scatter(
                        x=forecast_segment.index,
                        y=forecast_segment.values,
                        mode='lines',
                        name=sensor_name + " (Forecast)",
                        line=dict(color=color, dash='dash', width=2),
                        legendgroup=sensor_name,
                        showlegend=False
                    ))
            else:
                # No real data, just show forecast
                fig.add_trace(go.Scatter(
                    x=combined_data.index,
                    y=combined_data.values,
                    mode='lines',
                    name=sensor_name,
                    line=dict(color=color, dash='dash', width=2)
                ))
        else:
            # No real data, just show prediction
            fig.add_trace(go.Scatter(
                x=pred_data.index,
                y=pred_data.values,
                mode='lines',
                name=sensor_name,
                line=dict(color=color, dash='dash', width=2)
            ))
    
    fig.update_layout(
        title="Forecasted energy production",
        xaxis_title="Time",
        yaxis_title="Forecasted energy production (Unit)",
        hovermode='x unified',
        height=500,
        template="plotly_white"
    )
    
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Preview Raw Data"):
        if combined_real is not None:
            combined_with_real = combined_pred.join(combined_real, how="outer")
            st.dataframe(combined_with_real.reset_index().head(200))
        else:
            st.dataframe(combined_pred.reset_index().head(200))

st.caption(
    f"Showing window: **{start_time.strftime('%Y-%m-%d %H:%M')} → {end_time.strftime('%Y-%m-%d %H:%M')} (UTC)**"
)
