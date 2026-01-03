
import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from entsoe import Area, EntsoePandasClient
import openmeteo_requests
import requests_cache
from pandas import Timestamp
from retry_requests import retry
import matplotlib.dates as mdates

from data.Constants import WEATHER_FEATURES, ENERGY_FEATURES

def get_entsoe_data(section: str, start_date: Timestamp, end_date: Timestamp, api_key: str):
    client = EntsoePandasClient(api_key=api_key)
    try:
        df = client.query_generation(country_code=Area[section.upper()], start=start_date, end=end_date)
    except Exception as e:
        print(f"Error fetching Energy data for section {section}: {e}")
        return None

    df.dropna()

    col_filter = [col for col in df.columns if col in ENERGY_FEATURES]
    df = df[col_filter]
    df = df.rename(columns={'Wind Onshore': 'wind'})
    df = df.rename(columns={'Solar': 'solar'})

    df = df.reset_index()
    df = df.rename(columns={'index': 'timestamp'})
    df["section"] = section

    return df

def get_meteo_data(url: str, params: dict):
    # Setup the Open-Meteo API client with cache and retry on error
    cache_session = requests_cache.CachedSession('.cache', expire_after = -1)
    retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
    openmeteo = openmeteo_requests.Client(session = retry_session)

    responses = openmeteo.weather_api(url, params=params)

    # Process first location
    response = responses[0]

    # Process hourly data. The order of variables needs to be the same as requested.
    hourly = response.Hourly()

    hourly_data = {"timestamp": pd.date_range(
        start = pd.to_datetime(hourly.Time(), unit = "s"),
        end = pd.to_datetime(hourly.TimeEnd(), unit = "s"),
        freq = pd.Timedelta(seconds = hourly.Interval()),
        inclusive = "left"
    )}

    for i in range(len(WEATHER_FEATURES)):
        hourly_data[WEATHER_FEATURES[i]] = hourly.Variables(i).ValuesAsNumpy()

    hourly_dataframe = pd.DataFrame(data = hourly_data)
    hourly_dataframe = hourly_dataframe.dropna()
    return hourly_dataframe


def get_historical_weather(start_date,  end_date, latitude, longitude):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": WEATHER_FEATURES
    }

    return get_meteo_data(url, params)

def get_hourly_weather_forecast(latitude, longitude, time):
    url = "https://api.open-meteo.com/v1/ecmwf"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": WEATHER_FEATURES,
        "forecast_days": 3
    }

    df = get_meteo_data(url, params)

    # forecast contains data for next 72 hours (starting at 00:00 of today, but we only need the next 24 hours starting from current hour)
    df = df[df['timestamp'] >= time]
    df = df.head(24)
    return df

def get_historical_energy_production(start_date,  end_date, section, api_key):
    return get_entsoe_data(section, start_date, end_date, api_key)

def get_hourly_energy_production(section: str, time: datetime.datetime, api_key):
    end = pd.Timestamp(time, tz='Europe/Stockholm').floor('h')
    start = end - pd.Timedelta(hours=2)

    df = get_entsoe_data(section, start, end, api_key)
    if df.empty:
        print(f"No Energy data for section {section} at time {time}")
        return None

    # df contains multiple data points (15min interval) -> take first one
    df = df.head(1)
    return df

def plot_energy_forecast(section: str, energy_source: str, df: pd.DataFrame, file_path: str, hindcast=False):
    fig, ax = plt.subplots(figsize=(10, 6))

    day = pd.to_datetime(df['timestamp']).dt.date
    # Plot each column separately in matplotlib
    ax.plot(day, df['predicted_energy'], label=f'Predicted {energy_source}', color='red', linewidth=2, marker='o', markersize=5, markerfacecolor='blue')

    num_ticks_interval = max(1, int(np.ceil(len(day) / 10)))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=num_ticks_interval))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

    # Set the y-axis to a logarithmic scale
    if energy_source == 'solar':
        ax.get_yaxis().set_major_formatter(plt.ScalarFormatter())
        ax.set_ylim(bottom=0)
    else:
        ax.set_yscale('log')
        ax.set_yticks([0, 50, 100, 250, 500, 1000, 2000, 5000])
        ax.get_yaxis().set_major_formatter(plt.ScalarFormatter())
        ax.set_ylim(bottom=1)

    # Set the labels and title
    ax.set_xlabel('Timestamp')
    ax.set_title(f"{energy_source} predicted (Logarithmic Scale) for {section}")
    ax.set_ylabel(f'{energy_source} Energy Production (MWh)')

    # Aim for ~10 annotated values on x-axis, will work for both forecasts ans hindcasts
    # if len(df.index) > 25:
    #     every_x_tick = len(df.index) / 800
    #     ax.xaxis.set_major_locator(MultipleLocator(every_x_tick))

    plt.xticks(rotation=45)

    if hindcast:
        ax.plot(day, df[energy_source], label=f'Actual {energy_source}', color='black', linewidth=2, marker='^', markersize=5, markerfacecolor='grey')
        legend2 = ax.legend(loc='upper left', fontsize='x-small')

    # Ensure everything is laid out neatly
    plt.tight_layout()

    # # Save the figure, overwriting any existing file with the same name
    plt.savefig(file_path)
    return plt


def backfill_predictions_for_monitoring(weather_fg, energy_fg, monitor_fg, model, energy_source):
    features_df = weather_fg.read()
    features_df = features_df.sort_values(by=['timestamp'], ascending=True)
    features_df = transform_timestamp(features_df)
    features_df = features_df.tail(30)
    features_df['predicted_energy'] = model.predict(features_df[WEATHER_FEATURES+["hour", "day_of_week", "month", "day_of_year"]])
    df = pd.merge(features_df, energy_fg[['timestamp', energy_source]], on="timestamp")
    df['hours_before_forecast'] = 1
    hindcast_df = df
    print("Backfilled hindcast predictions:")
    print(df.head(15))
    df = df.drop(energy_source, axis=1)
    monitor_fg.insert(df, write_options={"wait_for_job": True})
    return hindcast_df

def transform_timestamp(df_in: pd.DataFrame) -> pd.DataFrame:
    df = df_in.copy()
    df_in['timestamp'] = pd.to_datetime(df_in['timestamp'])
    # Extract relevant features for energy prediction
    df['hour'] = df_in['timestamp'].dt.hour
    df['day_of_week'] = df_in['timestamp'].dt.dayofweek
    df['month'] = df_in['timestamp'].dt.month
    df['day_of_year'] = df_in['timestamp'].dt.dayofyear

    return df
