EARLIEST_HISTORICAL_DATE = "2022-01-01"

LOCATIONS = [
    ["SE_1", 66.83197545465562, 21.09658182376257],
    ["SE_2", 63.41704926197734, 16.087507002857887],
    ["SE_3", 59.44841932603451, 15.36155412007809],
    ["SE_4", 56.45704350532567, 14.224629482085703]
]

WEATHER_FEATURES = ["temperature_2m", "wind_speed_100m", "wind_direction_100m", "surface_pressure",
                    "relative_humidity_2m", "sunshine_duration"]

PREDICTION_FEATURES = {
    "wind": ["temperature_2m", "wind_dir_sin", "wind_dir_cos", "surface_pressure",
             "relative_humidity_2m", "wind_speed_cubed", "wind_power_density", "hour_sin", "hour_cos",
             "day_of_week_sin", "day_of_week_cos", "day_of_year_sin", "day_of_year_cos"],
    "solar": ["temperature_2m", "wind_speed_100m", "wind_dir_sin", "wind_dir_cos", "surface_pressure",
              "relative_humidity_2m", "sunshine_duration", "sun_elevation", "sun_azimuth", "hour_sin", "hour_cos",
              "day_of_week_sin", "day_of_week_cos", "day_of_year_sin", "day_of_year_cos"]
}

ENERGY_FEATURES = ["Solar", "Wind Onshore"]
