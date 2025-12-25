from pathlib import Path
import hopsworks
import sys

root_dir = Path().absolute()
if root_dir.parts[-1:] == ("utils",):
    root_dir = Path(*root_dir.parts[:-1])
root_dir = root_dir.resolve()
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

if root_dir not in sys.path:
    sys.path.append(root_dir)
    print(f"Added to PYTHONPATH: {root_dir}")

from data.Constants import LOCATIONS

files_to_clean=""
if len(sys.argv) != 2:
    print("Usage: <prog> project_to_clean (e.g., cc or aq or titanic)")
    sys.exit(1)

files_to_clean = sys.argv[1]

print(f"Cleaning project: {files_to_clean}")

project = hopsworks.login(engine="python") 

# Get feature store, deployment registry, model registry
fs = project.get_feature_store()
ms = project.get_model_serving()
mr = project.get_model_registry()
kafka_api = project.get_kafka_api()

def delete_model(model_name):
    try:
        models = mr.get_models(name=model_name)
        for model in models:
            print(f"Deleting model: {model.name} (version: {model.version})")
            try:
                model.delete()
            except Exception:
                print(f"Failed to delete model {model_name}.")
    except Exception:
        print("No  models to delete.")

def delete_feature_view(feature_view):
    # Get all feature views
    try:
        feature_views = fs.get_feature_views(name=feature_view)
    except:
        print(f"Couldn't find feature view: {feature_view}. Skipping...")
        feature_views = []

    # Delete each feature view
    for fv in feature_views:
        print(f"Deleting feature view: {fv.name} (version: {fv.version})")
        try:
            fv.delete()
        except Exception:
            print(f"Failed to delete feature view {fv.name}.")

def delete_feature_group(feature_group):
    # Get all feature groups
    try:
        feature_groups = fs.get_feature_groups(name=feature_group)
    except:
        print(f"Couldn't find feature group: {feature_group}. Skipping...")
        feature_groups = []

    # Delete each feature group
    for fg in feature_groups:
        print(f"Deleting feature group: {fg.name} (version: {fg.version})")
        try:
            fg.delete()
        except:
            print(f"Failed to delete feature group {fg.name}.")

    try:
        kafka_topics = kafka_api.get_topics()
        for topic in kafka_topics:
            if topic.name == feature_group:
                topic.delete()
                print(f"Deleting kafka topic {feature_group}")
    except:
        print(f"Couldn't find any kafka topics. Skipping...")

    try:
        schema = kafka_api.get_schema(feature_group, 1)
        if schema is not None:
            schema.delete()
    except:
        print(f"Couldn't find kafka schema: {feature_group}. Skipping...")



if files_to_clean == "gef":
    energy_sources = ["wind", "solar"]
    for location in LOCATIONS:
        for energy_source in energy_sources:
            section = location[0]

            delete_model(f"{energy_source}_xgboost_model_{section.lower()}")
            delete_feature_view(f"{energy_source}_energy_production_fv_{section.lower()}")
            for feature_group in [
                f"energy_production_{section.lower()}",
                f"weather_{section.lower()}",
                f"{energy_source}_energy_predictions_{section.lower()}",
            ]:
                delete_feature_group(feature_group)

