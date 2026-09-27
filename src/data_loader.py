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
    co2_cap_df: Optional[pd.DataFrame] = None
    battery_df: Optional[pd.DataFrame] = None

def load_default_data() -> DataBundle:
    """Load the bundled default dataset."""
    demand_df = pd.read_csv(DATA_DIR / "demand.csv")
    solar_df = pd.read_csv(DATA_DIR / "solar_availability.csv")
    wind_df = pd.read_csv(DATA_DIR / "wind_availability.csv")
    generators_df = pd.read_csv(DATA_DIR / "generators.csv")

    co2_cap_df = None
    co2_path = DATA_DIR / "co2_cap.csv"
    if co2_path.exists():
        co2_cap_df = pd.read_csv(co2_path)

    battery_df = None
    battery_path = DATA_DIR / "battery.csv"
    if battery_path.exists():
        battery_df = pd.read_csv(battery_path)

    return DataBundle(
        demand_df=demand_df,
        solar_df=solar_df,
        wind_df=wind_df,
        generators_df=generators_df,
        co2_cap_df=co2_cap_df,
        battery_df=battery_df,
    )

def load_8760_data() -> DataBundle:
    """Load the full-year 8,760-hour dataset."""
    dir_8760 = DATA_DIR.parent / "data_8760"
    
    demand_df = pd.read_csv(dir_8760 / "demand.csv")
    solar_df = pd.read_csv(dir_8760 / "solar_availability.csv")
    wind_df = pd.read_csv(dir_8760 / "wind_availability.csv")
    generators_df = pd.read_csv(dir_8760 / "generators.csv")
    
    # We must replace repeating `hour` (0-23) with a strictly chronological t=0..8759
    for df in [demand_df, solar_df, wind_df]:
        if "hour" in df.columns:
            df.rename(columns={"hour": "hour_of_day"}, inplace=True)
        df["hour"] = range(len(df))

    # Read CO2 caps (not in 8760 by default, let's copy behavior from default but stretch it if needed, 
    # but the simplest is just use None, so the user can configure a flat cap via UI or we use battery_df)
    co2_cap_df = None
    
    # We can reuse the existing battery parameter CSV since it has no time dimension
    battery_df = None
    battery_path = DATA_DIR / "battery.csv"
    if battery_path.exists():
        battery_df = pd.read_csv(battery_path)
        
    return DataBundle(
        demand_df=demand_df,
        solar_df=solar_df,
        wind_df=wind_df,
        generators_df=generators_df,
        co2_cap_df=co2_cap_df,
        battery_df=battery_df,
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


def build_phase2_config(bundle: DataBundle, overrides: dict = None) -> 'Phase2Config':
    """Build a Phase2Config from a DataBundle and optional UI overrides.
    
    Returns a Phase2Config instance with settings derived from data files 
    and overrides dict.
    """
    from src.optimizer import Phase2Config
    
    cfg = Phase2Config()
    ov = overrides or {}

    # Ramp config from generators
    gen = bundle.generators_df
    thermal_row = gen[gen["source"] == "Thermal"]
    if not thermal_row.empty and "ramp_limit_mw_per_hour" in gen.columns:
        ramp_val = thermal_row["ramp_limit_mw_per_hour"].values[0]
        if pd.notna(ramp_val) and float(ramp_val) > 0:
            cfg.ramp_limit_mw_per_hour = float(ramp_val)

    cfg.enable_ramp = ov.get("enable_ramp", False)
    cfg.initial_thermal_output_mw = float(ov.get("initial_thermal_output_mw", 400.0))

    # CO2 cap
    cfg.enable_co2_cap = ov.get("enable_co2_cap", False)
    if bundle.co2_cap_df is not None:
        cfg.co2_cap_df = bundle.co2_cap_df.copy()

    # Battery
    cfg.enable_battery = ov.get("enable_battery", False)
    if bundle.battery_df is not None:
        batt = bundle.battery_df.set_index("parameter")["value"]
        cfg.battery_capacity_mwh = float(batt.get("capacity_mwh", 400))
        cfg.charge_rate_max_mw = float(batt.get("charge_rate_max_mw", 100))
        cfg.discharge_rate_max_mw = float(batt.get("discharge_rate_max_mw", 100))
        cfg.charge_efficiency = float(batt.get("charge_efficiency", 0.90))
        cfg.discharge_efficiency = float(batt.get("discharge_efficiency", 0.90))
        cfg.initial_soc_mwh = float(batt.get("initial_soc_mwh", 200))
        cfg.min_soc_mwh = float(batt.get("min_soc_mwh", 40))
        cfg.max_soc_mwh = float(batt.get("max_soc_mwh", 360))

    # Reliability mode
    cfg.enable_reliability = ov.get("enable_reliability", False)
    cfg.unmet_demand_penalty = float(ov.get("unmet_demand_penalty", 50000.0))

    return cfg
