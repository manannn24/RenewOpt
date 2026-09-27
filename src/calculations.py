import pandas as pd
from typing import Dict


def calculate_total_cost(dispatch_df: pd.DataFrame) -> float:
    """Total generation cost = sum of hour_total_cost across all hours."""
    return float(dispatch_df["hour_total_cost"].sum())


def calculate_renewable_generation(dispatch_df: pd.DataFrame) -> float:
    """Total renewable generation = sum of solar + wind MWh."""
    return float((dispatch_df["solar_mw"] + dispatch_df["wind_mw"]).sum())


def calculate_total_generation(dispatch_df: pd.DataFrame) -> float:
    """Total generation across all hours."""
    return float(dispatch_df["total_generation_mw"].sum())


def calculate_renewable_share(dispatch_df: pd.DataFrame) -> float:
    """
    Renewable share (%) = (solar + wind) / total_generation * 100.
    Returns 0.0 if total generation is zero.
    """
    total = calculate_total_generation(dispatch_df)
    if total < 1e-9:
        return 0.0
    renewable = calculate_renewable_generation(dispatch_df)
    return float(renewable / total * 100.0)


def calculate_thermal_dependency(dispatch_df: pd.DataFrame) -> float:
    """
    Thermal dependency (%) = thermal_generation / total_generation * 100.
    Returns 0.0 if total generation is zero.
    """
    total = calculate_total_generation(dispatch_df)
    if total < 1e-9:
        return 0.0
    thermal = float(dispatch_df["thermal_mw"].sum())
    return float(thermal / total * 100.0)


def calculate_total_emissions(dispatch_df: pd.DataFrame, generators_df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate CO2 emissions (kg) per source and total.
    Emission for source s = generation_s * co2_per_mwh_s
    """
    gen = generators_df.set_index("source")
    co2_solar = float(gen.loc["Solar", "co2_per_mwh"])
    co2_wind = float(gen.loc["Wind", "co2_per_mwh"])
    co2_thermal = float(gen.loc["Thermal", "co2_per_mwh"])

    solar_emissions = float(dispatch_df["solar_mw"].sum()) * co2_solar
    wind_emissions = float(dispatch_df["wind_mw"].sum()) * co2_wind
    thermal_emissions = float(dispatch_df["thermal_mw"].sum()) * co2_thermal
    total_emissions = solar_emissions + wind_emissions + thermal_emissions

    return {
        "solar_kg_co2": solar_emissions,
        "wind_kg_co2": wind_emissions,
        "thermal_kg_co2": thermal_emissions,
        "total_kg_co2": total_emissions,
    }


def calculate_source_costs(dispatch_df: pd.DataFrame) -> Dict[str, float]:
    """Return per-source and total generation costs."""
    return {
        "solar_cost": float(dispatch_df["solar_cost"].sum()),
        "wind_cost": float(dispatch_df["wind_cost"].sum()),
        "thermal_cost": float(dispatch_df["thermal_cost"].sum()),
        "total_cost": calculate_total_cost(dispatch_df),
    }


def build_metrics(dispatch_df: pd.DataFrame, generators_df: pd.DataFrame) -> Dict:
    """Compute all derived metrics from an optimal dispatch DataFrame."""
    emissions = calculate_total_emissions(dispatch_df, generators_df)
    costs = calculate_source_costs(dispatch_df)

    metrics = {
        "total_demand_mwh": float(dispatch_df["demand_mw"].sum()),
        "total_generation_mwh": calculate_total_generation(dispatch_df),
        "renewable_generation_mwh": calculate_renewable_generation(dispatch_df),
        "renewable_share_pct": calculate_renewable_share(dispatch_df),
        "thermal_dependency_pct": calculate_thermal_dependency(dispatch_df),
        **costs,
        **emissions,
    }

    # Phase 2 metrics (battery, unmet demand, shadow prices)
    if "charge_mw" in dispatch_df.columns:
        metrics["total_charge_mwh"] = float(dispatch_df["charge_mw"].sum())
        metrics["total_discharge_mwh"] = float(dispatch_df["discharge_mw"].sum())
        metrics["peak_soc_mwh"] = float(dispatch_df["soc_mwh"].max())
        metrics["min_soc_mwh"] = float(dispatch_df["soc_mwh"].min())
    if "unmet_mw" in dispatch_df.columns:
        metrics["total_unmet_mwh"] = float(dispatch_df["unmet_mw"].sum())
    if "shadow_price" in dispatch_df.columns:
        metrics["avg_shadow_price"] = float(dispatch_df["shadow_price"].mean())
        metrics["max_shadow_price"] = float(dispatch_df["shadow_price"].max())
    if "thermal_co2_kg" in dispatch_df.columns:
        metrics["peak_hourly_co2_kg"] = float(dispatch_df["thermal_co2_kg"].max())

    # Peak thermal output
    metrics["peak_thermal_mw"] = float(dispatch_df["thermal_mw"].max())

    return metrics
