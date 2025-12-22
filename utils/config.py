from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class HopsworksSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )
    
    MLFS_DIR: Path = Path(__file__).parent

    # For hopsworks.login(), set as environment variables if they are not already set as env variables
    HOPSWORKS_API_KEY: SecretStr | None = None
    HOPSWORKS_PROJECT: str | None = None
    HOPSWORKS_HOST: str | None = None

    ENTSOE_API_KEY: str | None = None

    # Personalized Recommendations
    TWO_TOWER_MODEL_EMBEDDING_SIZE: int = 16
    TWO_TOWER_MODEL_BATCH_SIZE: int = 2048
    TWO_TOWER_NUM_EPOCHS: int = 10
    TWO_TOWER_WEIGHT_DECAY: float = 0.001
    TWO_TOWER_LEARNING_RATE: float = 0.01
    TWO_TOWER_DATASET_VALIDATON_SPLIT_SIZE: float = 0.1
    TWO_TOWER_DATASET_TEST_SPLIT_SIZE: float = 0.1

    RANKING_DATASET_VALIDATON_SPLIT_SIZE: float = 0.1
    RANKING_LEARNING_RATE: float = 0.2
    RANKING_ITERATIONS: int = 100
    RANKING_SCALE_POS_WEIGHT: int = 10
    RANKING_EARLY_STOPPING_ROUNDS: int = 5

    # Inference
    RANKING_MODEL_TYPE: Literal["ranking", "llmranking"] = "ranking"
    CUSTOM_HOPSWORKS_INFERENCE_ENV: str = "custom_env_name"

    def model_post_init(self, __context):
        """Runs after the model is initialized."""
        print("HopsworksSettings initialized!")

        # Set environment variables if not already set
        if os.getenv("HOPSWORKS_API_KEY") is None:
            if self.HOPSWORKS_API_KEY is not None:
                os.environ['HOPSWORKS_API_KEY'] = self.HOPSWORKS_API_KEY.get_secret_value()
        if os.getenv("HOPSWORKS_PROJECT") is None:
            if self.HOPSWORKS_PROJECT is not None:
                os.environ['HOPSWORKS_PROJECT'] = self.HOPSWORKS_PROJECT
        if os.getenv("HOPSWORKS_HOST") is None:
            if self.HOPSWORKS_HOST is not None:
                os.environ['HOPSWORKS_HOST'] = self.HOPSWORKS_HOST

        # --- Check required .env values ---
        missing = []
        # 1. HOPSWORKS_API_KEY
        api_key = self.HOPSWORKS_API_KEY or os.getenv("HOPSWORKS_API_KEY")
        if not api_key:
            missing.append("HOPSWORKS_API_KEY")
        # 2. ENTSOE_API_KEY
        entsoe_api_key = self.ENTSOE_API_KEY or os.getenv("ENTSOE_API_KEY")
        if not entsoe_api_key:
            missing.append("ENTSOE_API_KEY")
            
        if missing:
            raise ValueError(
                "The following required settings are missing from your environment (.env or system):\n  " +
                "\n  ".join(missing)
            )    