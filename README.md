# Green Energy Forecast

**[Energy Forecast Dashboard](https://green-energy-forecast.streamlit.app/)**

An end-to-end, serverless Machine Learning system designed to predict hourly power generation for wind and solar assets in Sweden. The system provides **24-hour day-ahead forecasts** at a regional level (SE1–SE4).

## Problem Definition

The objective is to solve a regression problem where the target variable is the power generation (Wind and Solar) for a specific region in Sweden at time $t$.

* **Input:** Historical and forecasted meteorological data (wind speed, irradiance, temperature, cloud cover).
* **Target:** Actual aggregated generation data provided by transmission system operators.
* **Horizon:** Day-Ahead (on an hourly level).

## Technical Architecture

The project follows the **Feature-Training-Inference (FTI)** pattern, utilizing a serverless architecture to minimize infrastructure costs while maximizing scalability.

### 1. Feature Engineering Pipeline
This pipeline runs daily via scheduled cron jobs. Beyond basic ingestion of the weather features, it applies domain-specific transformations to improve model accuracy:

* **Temporal Encoding:** To capture the cyclical nature of energy production, time features are transformed using sin/cos encoding (e.g., hour of day, day of week). This allows the model to understand that hour 23 and hour 00 are chronologically adjacent.
* **Solar Geometry:** We calculate the Sun Elevation Angle and Azimuth for each region. This provides a physical constraint for solar forecasts, helping the model learn that production is impossible when the sun is below the horizon.
* **Storage:** Computed features are materialized into the **Hopsworks Feature Store**, providing a consistent offline store for training and a low-latency online store for inference.

### 2. Training Pipeline
Triggered weekly or upon significant data drift, this pipeline:
* Creates a training dataset from the Feature Store.
* Trains a XGB regression model.

### 3. Inference & User Interface
A deployment pipeline runs hourly to fetch the latest weather forecast, retrieve the model from the registry, and generate predictions for the next 24 hours.

The results are visualized in an interactive public dashboard built with **Streamlit**, allowing for real-time comparison between predicted and actual generation across Swedish bidding zones.



## Tech Stack

* **Platform:** Hopsworks (Feature Store & Model Registry)
* **Compute:** GitHub Actions
* **Dashboard:** [Streamlit](https://green-energy-forecast.streamlit.app/)
* **Data Sources:** Open-Meteo API (Weather), ENTSO-E Transparency Platform (Grid Data)

---

### Authors
* **Christoph Thees**
* **Simon Pernegger**

*Developed as part of the ID2223 Scalable Machine Learning and Deep Learning course at KTH Royal Institute of Technology.*