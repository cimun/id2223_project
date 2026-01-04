#!/usr/bin/env python3
import sys
import warnings
from pathlib import Path
from datetime import date

warnings.filterwarnings("ignore")

# ---------- Paths / PYTHONPATH ----------
root_dir = Path().absolute()
root_dir = root_dir.resolve()
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

if root_dir not in sys.path:
    sys.path.append(root_dir)
    print(f"Added to PYTHONPATH: {root_dir}")

# ---------- Settings ----------
from utils import config
settings = config.HopsworksSettings(_env_file=str(root_dir / ".env"))

# ---------- Imports ----------
import pandas as pd
import hopsworks
import great_expectations as ge
from utils import util
from data.Constants import LOCATIONS, EARLIEST_HISTORICAL_DATE
from utils.util import transform_timestamp

# ---------- Hopsworks login ----------
project = hopsworks.login(engine="python")
fs = project.get_feature_store()

# ---------- Helpers ----------

def process_sensor(location: list, today: date) -> None:
    section = location[0]
    latitude  = location[1]
    longitude = location[2]
    print(f"\n=== Processing Section: {section} ===")

    energy_df = util.get_historical_energy_production(pd.Timestamp(EARLIEST_HISTORICAL_DATE, tz='Europe/Stockholm'),
                                                      pd.Timestamp(today, tz='Europe/Stockholm'),
                                                      section, settings.ENTSOE_API_KEY)


    # subtract 1 day to ensure coverage
    weather_df = util.get_historical_weather(EARLIEST_HISTORICAL_DATE, today, latitude, longitude)
    weather_df["section"] = section

    weather_df = transform_timestamp(weather_df)

    # Feature Groups (per section, suffixed)
    energy_fg_name = f"energy_production_{section.lower()}"
    weather_fg_name = f"weather_{section.lower()}"

    energy_production_fg = fs.get_or_create_feature_group(
        name=energy_fg_name,
        description=f"Wind and solar energy production per hour ({section})",
        version=1,
        primary_key=["section"],
        event_time="timestamp"
    )

    energy_production_fg.insert(energy_df)
    energy_production_fg.update_feature_description("timestamp", "Timestamp of weather measurement")
    energy_production_fg.update_feature_description("section", "Section in which energy is produced")
    energy_production_fg.update_feature_description("wind", "Wind energy production (MW)")
    energy_production_fg.update_feature_description("solar", "Solar energy production (MW)")

    weather_fg = fs.get_or_create_feature_group(
        name=weather_fg_name,
        description=f"Weather per hour ({section})",
        version=1,
        primary_key=["section"],
        event_time="timestamp",
    )
    weather_fg.insert(weather_df, wait=True)
    weather_fg.update_feature_description("timestamp", "Timestamp of weather measurement")
    weather_fg.update_feature_description("section", "Section for weather")
    weather_fg.update_feature_description("temperature_2m", "Outside temperature (Celsius)")
    weather_fg.update_feature_description("wind_speed_100m", "Wind speed at 100m (m/s)")
    weather_fg.update_feature_description("surface_pressure", "Surface pressure (hPa)")
    weather_fg.update_feature_description("relative_humidity_2m", "Relative humidity at 2m (%)")
    weather_fg.update_feature_description("sunshine_duration", "Sunshine duration (seconds)")

    print(f"✓ Completed: {section}")

# ---------- Main ----------
def main():
    today = date.today()

    for location in LOCATIONS:
        try:
            process_sensor(location, today)
        except Exception as e:
            print(f"! Error processing {location[0]}: {e}")

    print("\nAll sections processed.")

if __name__ == "__main__":
    main()
