import pandas as pd
from dataclasses import dataclass
from typing import Optional, Dict
from src.optimizer import solve_dispatch, OptimizationResult
from src.calculations import build_metrics
from src.validation import validate_data, check_feasibility

@dataclass
class ScenarioResult:
    name: str
    description: str
    status: str
    result: OptimizationResult
    metrics: Optional[Dict] = None

def run_scenario(
    name: str,
    description: str,
    demand_df: pd.DataFrame,
    solar_df: pd.DataFrame,
    wind_df: pd.DataFrame,
    generators_df: pd.DataFrame,
) -> ScenarioResult:
    """Run a single scenario and return its result."""
    result = solve_dispatch(demand_df, solar_df, wind_df, generators_df)
    metrics = None
    if result.status == "Optimal" and result.dispatch_df is not None:
        metrics = build_metrics(result.dispatch_df, generators_df)
    return ScenarioResult(
        name=name,
        description=description,
        status=result.status,
        result=result,
        metrics=metrics,
    )

def run_baseline(
    demand_df: pd.DataFrame,
    solar_df: pd.DataFrame,
    wind_df: pd.DataFrame,
    generators_df: pd.DataFrame,
) -> ScenarioResult:
    """Scenario 1: Baseline - no modifications."""
    return run_scenario(
        name="Baseline",
        description="Normal operating conditions with default dataset.",
        demand_df=demand_df.copy(),
        solar_df=solar_df.copy(),
        wind_df=wind_df.copy(),
        generators_df=generators_df.copy(),
    )

def run_high_demand(
    demand_df: pd.DataFrame,
    solar_df: pd.DataFrame,
    wind_df: pd.DataFrame,
    generators_df: pd.DataFrame,
    multiplier: float = 1.20,
) -> ScenarioResult:
    """Scenario 2: High Demand - increase demand by multiplier."""
    demand_mod = demand_df.copy()
    demand_mod["demand_mw"] = demand_mod["demand_mw"] * multiplier
    return run_scenario(
        name="High Demand",
        description=f"Demand increased by {(multiplier-1)*100:.0f}%.",
        demand_df=demand_mod,
        solar_df=solar_df.copy(),
        wind_df=wind_df.copy(),
        generators_df=generators_df.copy(),
    )

def run_low_solar(
    demand_df: pd.DataFrame,
    solar_df: pd.DataFrame,
    wind_df: pd.DataFrame,
    generators_df: pd.DataFrame,
    multiplier: float = 0.50,
) -> ScenarioResult:
    """Scenario 3: Low Solar - reduce solar availability by (1-multiplier)."""
    solar_mod = solar_df.copy()
    solar_mod["solar_available_mw"] = solar_mod["solar_available_mw"] * multiplier
    return run_scenario(
        name="Low Solar",
        description=f"Solar availability reduced to {multiplier*100:.0f}% of normal.",
        demand_df=demand_df.copy(),
        solar_df=solar_mod,
        wind_df=wind_df.copy(),
        generators_df=generators_df.copy(),
    )

def run_high_thermal_cost(
    demand_df: pd.DataFrame,
    solar_df: pd.DataFrame,
    wind_df: pd.DataFrame,
    generators_df: pd.DataFrame,
    multiplier: float = 1.30,
) -> ScenarioResult:
    """Scenario 4: High Thermal Cost - increase thermal cost per MWh."""
    gen_mod = generators_df.copy()
    gen_mod.loc[gen_mod["source"] == "Thermal", "cost_per_mwh"] = (
        gen_mod.loc[gen_mod["source"] == "Thermal", "cost_per_mwh"] * multiplier
    )
    return run_scenario(
        name="High Thermal Cost",
        description=f"Thermal generation cost increased by {(multiplier-1)*100:.0f}%.",
        demand_df=demand_df.copy(),
        solar_df=solar_df.copy(),
        wind_df=wind_df.copy(),
        generators_df=gen_mod,
    )

def run_increased_renewable_capacity(
    demand_df: pd.DataFrame,
    solar_df: pd.DataFrame,
    wind_df: pd.DataFrame,
    generators_df: pd.DataFrame,
    solar_capacity_addition_mw: float = 200.0,
) -> ScenarioResult:
    """
    Scenario 5: Increased Renewable Capacity - add solar capacity.
    Assumes the added solar capacity has the same normalized hourly generation profile
    as the existing capacity (i.e. scales proportionally).
    """
    solar_row = generators_df[generators_df["source"] == "Solar"]
    old_capacity = float(solar_row["max_capacity_mw"].values[0])
    new_capacity = old_capacity + solar_capacity_addition_mw
    ratio = new_capacity / old_capacity

    solar_mod = solar_df.copy()
    solar_mod["solar_available_mw"] = solar_mod["solar_available_mw"] * ratio
    # Cap at new capacity
    solar_mod["solar_available_mw"] = solar_mod["solar_available_mw"].clip(upper=new_capacity)

    gen_mod = generators_df.copy()
    gen_mod.loc[gen_mod["source"] == "Solar", "max_capacity_mw"] = new_capacity

    return run_scenario(
        name="Increased Renewable Capacity",
        description=f"Solar capacity increased by {solar_capacity_addition_mw:.0f} MW (to {new_capacity:.0f} MW).",
        demand_df=demand_df.copy(),
        solar_df=solar_mod,
        wind_df=wind_df.copy(),
        generators_df=gen_mod,
    )

def run_all_scenarios(
    demand_df: pd.DataFrame,
    solar_df: pd.DataFrame,
    wind_df: pd.DataFrame,
    generators_df: pd.DataFrame,
) -> Dict[str, ScenarioResult]:
    """Run all defined scenarios and return results dict."""
    return {
        "Baseline": run_baseline(demand_df, solar_df, wind_df, generators_df),
        "High Demand": run_high_demand(demand_df, solar_df, wind_df, generators_df),
        "Low Solar": run_low_solar(demand_df, solar_df, wind_df, generators_df),
        "High Thermal Cost": run_high_thermal_cost(demand_df, solar_df, wind_df, generators_df),
        "Increased Renewable Capacity": run_increased_renewable_capacity(demand_df, solar_df, wind_df, generators_df),
    }
