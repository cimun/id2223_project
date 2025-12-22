#!/usr/bin/env python3
import sys
import warnings
from pathlib import Path
from datetime import datetime
warnings.filterwarnings("ignore", module="IPython")

# ---------- Paths / PYTHONPATH ----------
root_dir = Path().absolute()
if root_dir.parts[-1:] == ("airquality",):
    root_dir = Path(*root_dir.parts[:-1])
if root_dir.parts[-1:] == ("notebooks",):
    root_dir = Path(*root_dir.parts[:-1])
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

from data.Constants import LOCATIONS
import hopsworks
from utils import util

# ---------- Hopsworks login ----------
project = hopsworks.login(engine="python")
fs = project.get_feature_store()

def process_sensor(location: list, time: datetime) -> None:
    section = location[0]
    latitude  = location[1]
    longitude = location[2]

    print(f"\n=== Hourly update: {section} ({time}) ===")

    #NOTE: ECMWF only updates predictions every 6 hours
    hourly_weather_df = util.get_hourly_weather_forecast(latitude, longitude, time) # needs to have 24 entries for next 24 hours
    hourly_weather_df["section"] = section

    hourly_energy_df = util.get_hourly_energy_production(section, time, settings.ENTSOE_API_KEY) # needs to have 1 entry for past hour

    # Per-sensor feature groups
    energy_fg = fs.get_feature_group(name=f"energy_production_{section.lower()}", version=1)
    wx_fg = fs.get_feature_group(name=f"weather_{section.lower()}", version=1)

    # Inserts
    energy_fg.insert(hourly_energy_df, wait=True)
    wx_fg.insert(hourly_weather_df, wait=True)

    print(f"✓ Completed: {section}")

# ---------- Main ----------
def main():
    now = datetime.now()

    for location in LOCATIONS:
        try:
            process_sensor(location, now)
        except Exception as e:
            print(f"! Error processing {location[0]}: {e}")

    print("\nAll sections processed.")

if __name__ == "__main__":
    main()
