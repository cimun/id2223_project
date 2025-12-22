import sys
import os
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
from xgboost import XGBRegressor, plot_importance
from sklearn.metrics import mean_squared_error, r2_score
import hopsworks
from utils import util
from data.Constants import LOCATIONS

# ---------- Hopsworks login ----------
if settings.HOPSWORKS_API_KEY is not None:
    os.environ["HOPSWORKS_API_KEY"] = settings.HOPSWORKS_API_KEY.get_secret_value()
project = hopsworks.login(engine="python")
fs = project.get_feature_store()
mr = project.get_model_registry()


def train_energy_prediction_model(location: dict, energy_source: str) -> None:
    section = location[0]

    energy_fg = fs.get_feature_group(name=f"energy_production_{section.lower()}", version=1)
    weather_fg = fs.get_feature_group(name=f"weather_{section.lower()}", version=1)

    selected = energy_fg.select(["timestamp", energy_source]).join(weather_fg.select_features(), on=["section"])
    fv = fs.get_or_create_feature_view(
        name=f"{energy_source}_energy_production_fv_{section.lower()}",
        description=f"Features for prediction {energy_source} energy in {section}",
        version=1,
        labels=[energy_source],
        query=selected,
    )

    # ---- start split for test data (our earliest date is 2022-01-01) ----
    start_date_test_data = "2025-01-01"
    # Convert string to datetime object
    test_start = datetime.strptime(start_date_test_data, "%Y-%m-%d")
    
    X_train, X_test, y_train, y_test = fv.train_test_split(test_start=test_start)
    X_features = X_train.drop(columns=["timestamp"])
    X_test_features = X_test.drop(columns=["timestamp"])

    model = XGBRegressor()
    model.fit(X_features, y_train)

    y_pred = model.predict(X_test_features)
    mse = mean_squared_error(y_test.iloc[:, 0], y_pred)
    r2 = r2_score(y_test.iloc[:, 0], y_pred)
    print(f"[{section}, {energy_source}] MSE={mse:.4f} R2={r2:.4f}")

    df = y_test.copy()
    df["predicted_energy"] = y_pred
    df["timestamp"] = X_test["timestamp"]
    df = df.sort_values(by=["timestamp"])

    out_dir = Path(f"{energy_source}_model_{section.lower()}")
    img_dir = out_dir / "images"
    out_dir.mkdir(exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    hindcast_path = img_dir / f"{energy_source}_hindcast.png"
    plt = util.plot_energy_forecast(section, energy_source, df, str(hindcast_path), hindcast=True)
    #plt.show()

    plot_importance(model)
    plt.savefig(img_dir / "feature_importance.png")
    #plt.show()

    model.save_model(str(out_dir / "model.json"))
    metrics = {"MSE": str(mse), "R squared": str(r2)}

    reg_name = f"{energy_source}_xgboost_model_{section.lower()}"
    py_model = mr.python.create_model(
        name=reg_name,
        metrics=metrics,
        feature_view=fv,
        description=f"{energy_source} energy predictor for {section}",
    )
    py_model.save(str(out_dir))
    print(f"[{section}, {energy_source}] Model saved to registry as {reg_name}")

# ---------- Main ----------
def main():

    for location in LOCATIONS:
        try:
            train_energy_prediction_model(location, "wind")
            train_energy_prediction_model(location, "solar")
        except Exception as e:
            print(f"! Error processing {location[0]}: {e}")

    print("\nAll sections processed.")

if __name__ == "__main__":
    main()
