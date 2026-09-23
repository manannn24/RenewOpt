import pandas as pd
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"

@dataclass
class DataBundle:
    demand_df: pd.DataFrame
    solar_df: pd.DataFrame
    wind_df: pd.DataFrame
    generators_df: pd.DataFrame

def load_default_data() -> DataBundle:
    """Load the bundled default dataset."""
    demand_df = pd.read_csv(DATA_DIR / "demand.csv")
    solar_df = pd.read_csv(DATA_DIR / "solar_availability.csv")
    wind_df = pd.read_csv(DATA_DIR / "wind_availability.csv")
    generators_df = pd.read_csv(DATA_DIR / "generators.csv")
    return DataBundle(
        demand_df=demand_df,
        solar_df=solar_df,
        wind_df=wind_df,
        generators_df=generators_df,
    )

def load_from_uploads(
    demand_file,
    solar_file,
    wind_file,
    generators_file,
) -> DataBundle:
    """Load datasets from uploaded file objects."""
    demand_df = pd.read_csv(demand_file)
    solar_df = pd.read_csv(solar_file)
    wind_df = pd.read_csv(wind_file)
    generators_df = pd.read_csv(generators_file)
    return DataBundle(
        demand_df=demand_df,
        solar_df=solar_df,
        wind_df=wind_df,
        generators_df=generators_df,
    )
