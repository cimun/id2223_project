#!/usr/bin/env python3
import sys
import traceback
import warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore", module="IPython")

# ---------- Paths / PYTHONPATH ----------
root_dir = Path().absolute()
root_dir = root_dir.resolve()
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))
print(f"Local environment — project root: {root_dir}")

if root_dir not in sys.path:
    sys.path.append(root_dir)
    print(f"Added to PYTHONPATH: {root_dir}")

# ---------- Settings ----------
from utils import config
settings = config.HopsworksSettings(_env_file=str(root_dir / ".env"))

# ---------- Imports ----------
import pandas as pd
from xgboost import XGBRegressor
import hopsworks
from utils import util
from data.Constants import LOCATIONS, WEATHER_FEATURES

# ---------- Hopsworks login ----------
project = hopsworks.login(engine="python")
fs = project.get_feature_store()
mr = project.get_model_registry()

def run_inference_for_sensor(location: dict, energy_source: str, current_time: datetime) -> None:
    """Run batch inference for one sensor, store results and upload PNGs."""
    section = location[0]
    print(f"\n=== Inference for {section} for energy source {energy_source} ({current_time}) ===")

    # ----- Load model -----
    model_name = f"{energy_source}_xgboost_model_{section.lower()}"
    try:
        model = mr.get_model(name=model_name, version=1)
    except Exception:
        print(f"! Model not found for {section}: {model_name}")
        return

    saved_model_dir = model.download()
    xgb_model = XGBRegressor()
    xgb_model.load_model(saved_model_dir + "/model.json")

    # ----- Load weather data -----
    weather_fg = fs.get_feature_group(name=f"weather_{section.lower()}", version=1)
    batch_df = weather_fg.filter(weather_fg.timestamp >= current_time).read()
    batch_df = batch_df.sort_values("timestamp")


    batch_df["predicted_energy"] = xgb_model.predict(batch_df[WEATHER_FEATURES+["hour", "day_of_week", "month", "day_of_year"]])

    batch_df["section"] = section
    batch_df["hours_before_forecast"] = range(1, len(batch_df) + 1)
    batch_df = batch_df.sort_values(by=["timestamp"])

    # ----- Save prediction chart -----
    docs_dir = root_dir / "docs" / "energy_forecast" / "assets" / "img"
    docs_dir.mkdir(parents=True, exist_ok=True)
    pred_path = docs_dir / f"{energy_source}_forecast_{section}.png"
    plt = util.plot_energy_forecast(section, energy_source, batch_df, str(pred_path))
    plt.close()

    # ----- Monitoring feature group -----
    monitor_fg = fs.get_or_create_feature_group(
        name=f"{energy_source}_energy_predictions_{section.lower()}",
        description=f"Energy ({energy_source}) prediction monitoring for {section}",
        version=1,
        primary_key=["section", "hours_before_forecast"],
        event_time="timestamp",
    )
    monitor_fg.insert(batch_df, wait=True)

    # ----- Hindcast -----
    energy_fg = fs.get_feature_group(name=f"energy_production_{section.lower()}", version=1)
    energy_df = energy_fg.read()
    outcome_df = energy_df[["timestamp", energy_source]]
    preds_df = monitor_fg.filter(monitor_fg.hours_before_forecast == 1).read()[
        ["timestamp", "predicted_energy"]
    ]

    hindcast_df = pd.merge(preds_df, outcome_df, on="timestamp", how="inner")
    hindcast_df = hindcast_df.sort_values(by=["timestamp"])
    if len(hindcast_df) == 0:
        hindcast_df = util.backfill_predictions_for_monitoring(
            weather_fg, energy_df, monitor_fg, xgb_model, energy_source
        )

    hindcast_path = docs_dir / f"{energy_source}_hindcast_{section}.png"
    plt = util.plot_energy_forecast(section, energy_source, hindcast_df, str(hindcast_path), hindcast=True)
    plt.close()

    # ----- Upload to Hopsworks -----
    dataset_api = project.get_dataset_api()
    today_str = current_time.strftime("%Y-%m-%d")
    hops_path = f"Resources/{energy_source}/{section}_{today_str}"
    if not dataset_api.exists(f"Resources/{energy_source}"):
        dataset_api.mkdir(f"Resources/{energy_source}")
    dataset_api.upload(str(pred_path), hops_path, overwrite=True)
    dataset_api.upload(str(hindcast_path), hops_path, overwrite=True)

    print(f"✓ Uploaded forecast and hindcast PNGs for {section} / {energy_source}")


# ---------- Main ----------
def main():
    now = datetime.now()

    for location in LOCATIONS:
        try:
            run_inference_for_sensor(location, "wind", now)
            run_inference_for_sensor(location, "solar", now)
        except Exception as e:
            print(f"! Error processing {location[0]}: {e}")
            traceback.print_exception(e)

    print("\nAll sections processed.")

if __name__ == "__main__":
    main()
