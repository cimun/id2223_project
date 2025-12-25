EARLIEST_HISTORICAL_DATE = "2022-01-01"

LOCATIONS = [
    # ["SE_1", 66.83197545465562, 21.09658182376257],
    # ["SE_2", 63.41704926197734, 16.087507002857887],
    # ["SE_3", 59.44841932603451, 15.36155412007809],
    ["SE_4", 56.45704350532567, 14.224629482085703]
]

WEATHER_FEATURES= ["temperature_2m", "precipitation", "wind_speed_10m", "wind_direction_10m", "surface_pressure",
                   "relative_humidity_2m", "cloud_cover", "sunshine_duration"]
# uv_index, sunshine_duration return NaN for historical data

ENERGY_FEATURES = ["Solar", "Wind Onshore"]