"""
RenewOpt Scenario Engine — Phase 1 + Phase 2 scenarios.

Phase 1 scenarios use the original solve_dispatch without Phase 2 config.
Phase 2 scenarios pass a Phase2Config to demonstrate advanced features.
"""

import pandas as pd
from dataclasses import dataclass
from typing import Optional, Dict
from src.optimizer import solve_dispatch, OptimizationResult, Phase2Config
from src.calculations import build_metrics


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
    phase2_config: Optional[Phase2Config] = None,
) -> ScenarioResult:
    """Run a single scenario and return its result."""
    result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, phase2_config)
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


# =============================================================================
# Phase 1 Scenarios (preserved exactly as before)
# =============================================================================

def run_baseline(demand_df, solar_df, wind_df, generators_df) -> ScenarioResult:
    """Scenario 1: Baseline - no modifications."""
    return run_scenario(
        name="Baseline",
        description="Normal operating conditions with default dataset.",
        demand_df=demand_df.copy(),
        solar_df=solar_df.copy(),
        wind_df=wind_df.copy(),
        generators_df=generators_df.copy(),
    )


def run_high_demand(demand_df, solar_df, wind_df, generators_df,
                    multiplier: float = 1.20) -> ScenarioResult:
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


def run_low_solar(demand_df, solar_df, wind_df, generators_df,
                  multiplier: float = 0.50) -> ScenarioResult:
    """Scenario 3: Low Solar - reduce solar availability."""
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


def run_high_thermal_cost(demand_df, solar_df, wind_df, generators_df,
                          multiplier: float = 1.30) -> ScenarioResult:
    """Scenario 4: High Thermal Cost."""
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


def run_increased_renewable_capacity(demand_df, solar_df, wind_df, generators_df,
                                     solar_capacity_addition_mw: float = 200.0) -> ScenarioResult:
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


def run_all_scenarios(demand_df, solar_df, wind_df, generators_df) -> Dict[str, ScenarioResult]:
    """Run all Phase 1 defined scenarios and return results dict."""
    return {
        "Baseline": run_baseline(demand_df, solar_df, wind_df, generators_df),
        "High Demand": run_high_demand(demand_df, solar_df, wind_df, generators_df),
        "Low Solar": run_low_solar(demand_df, solar_df, wind_df, generators_df),
        "High Thermal Cost": run_high_thermal_cost(demand_df, solar_df, wind_df, generators_df),
        "Increased Renewable Capacity": run_increased_renewable_capacity(demand_df, solar_df, wind_df, generators_df),
    }


# =============================================================================
# Phase 2 Scenarios
# =============================================================================

def run_phase2_extended_baseline(demand_df, solar_df, wind_df, generators_df,
                                 co2_cap_df=None) -> ScenarioResult:
    """Phase 2: Extended baseline — ramp + non-binding CO2 cap, no battery."""
    cfg = Phase2Config(
        enable_ramp=True,
        ramp_limit_mw_per_hour=200.0,
        initial_thermal_output_mw=400.0,
        enable_co2_cap=False,
        co2_cap_df=None,
        enable_battery=False,
    )
    return run_scenario(
        name="P2: Extended Baseline",
        description="Ramp constraints + CO2 cap enabled, no battery. Non-binding caps show ramp-only effects.",
        demand_df=demand_df.copy(),
        solar_df=solar_df.copy(),
        wind_df=wind_df.copy(),
        generators_df=generators_df.copy(),
        phase2_config=cfg,
    )


def run_phase2_tight_co2(demand_df, solar_df, wind_df, generators_df,
                         co2_cap_df=None) -> ScenarioResult:
    """Phase 2: Tight evening CO2 cap — no battery."""
    cfg = Phase2Config(
        enable_ramp=True,
        ramp_limit_mw_per_hour=200.0,
        initial_thermal_output_mw=400.0,
        enable_co2_cap=True,
        co2_cap_df=co2_cap_df,
        enable_battery=False,
        enable_reliability=True,
        unmet_demand_penalty=50000.0,
    )
    return run_scenario(
        name="P2: Tight CO2 (No Battery)",
        description="Tight evening CO2 cap forces thermal down. May produce unmet demand without battery.",
        demand_df=demand_df.copy(),
        solar_df=solar_df.copy(),
        wind_df=wind_df.copy(),
        generators_df=generators_df.copy(),
        phase2_config=cfg,
    )


def run_phase2_co2_with_battery(demand_df, solar_df, wind_df, generators_df,
                                co2_cap_df=None, battery_cfg=None) -> ScenarioResult:
    """Phase 2: Tight CO2 cap + battery storage — demonstrates inter-temporal optimization."""
    cfg = Phase2Config(
        enable_ramp=True,
        ramp_limit_mw_per_hour=200.0,
        initial_thermal_output_mw=400.0,
        enable_co2_cap=True,
        co2_cap_df=co2_cap_df,
        enable_battery=True,
        battery_capacity_mwh=400.0,
        charge_rate_max_mw=100.0,
        discharge_rate_max_mw=100.0,
        charge_efficiency=0.948,
        discharge_efficiency=0.948,
        initial_soc_mwh=0.0,
        min_soc_mwh=0.0,
        max_soc_mwh=400.0,
    )
    if battery_cfg:
        cfg.battery_capacity_mwh = battery_cfg.get("capacity_mwh", cfg.battery_capacity_mwh)
        cfg.charge_rate_max_mw = battery_cfg.get("charge_rate_max_mw", cfg.charge_rate_max_mw)
        cfg.discharge_rate_max_mw = battery_cfg.get("discharge_rate_max_mw", cfg.discharge_rate_max_mw)
    return run_scenario(
        name="P2: Tight CO2 + Battery",
        description="Battery pre-charges when thermal is cheap, discharges when CO2 cap binds. Inter-temporal LP behavior.",
        demand_df=demand_df.copy(),
        solar_df=solar_df.copy(),
        wind_df=wind_df.copy(),
        generators_df=generators_df.copy(),
        phase2_config=cfg,
    )


def run_phase2_insufficient_battery(demand_df, solar_df, wind_df, generators_df,
                                    co2_cap_df=None) -> ScenarioResult:
    """Phase 2: Tight CO2 cap + small battery — shows battery cannot fully compensate."""
    cfg = Phase2Config(
        enable_ramp=True,
        ramp_limit_mw_per_hour=200.0,
        initial_thermal_output_mw=400.0,
        enable_co2_cap=True,
        co2_cap_df=co2_cap_df,
        enable_battery=True,
        battery_capacity_mwh=50.0,
        charge_rate_max_mw=20.0,
        discharge_rate_max_mw=20.0,
        charge_efficiency=0.90,
        discharge_efficiency=0.90,
        initial_soc_mwh=25.0,
        min_soc_mwh=5.0,
        max_soc_mwh=45.0,
        enable_reliability=True,
        unmet_demand_penalty=50000.0,
    )
    return run_scenario(
        name="P2: Insufficient Battery",
        description="Small battery cannot compensate for tight CO2 cap. Some unmet demand expected.",
        demand_df=demand_df.copy(),
        solar_df=solar_df.copy(),
        wind_df=wind_df.copy(),
        generators_df=generators_df.copy(),
        phase2_config=cfg,
    )


def run_phase2_tight_ramp(demand_df, solar_df, wind_df, generators_df) -> ScenarioResult:
    """Phase 2: Very tight thermal ramp — shows inter-temporal positioning."""
    cfg = Phase2Config(
        enable_ramp=True,
        ramp_limit_mw_per_hour=80.0,
        initial_thermal_output_mw=400.0,
        enable_co2_cap=False,
        enable_battery=False,
        enable_reliability=True,
        unmet_demand_penalty=50000.0,
    )
    return run_scenario(
        name="P2: Tight Ramp (80 MW/hr)",
        description="Tight ramp forces thermal pre-positioning. May cause unmet demand at fast demand swings.",
        demand_df=demand_df.copy(),
        solar_df=solar_df.copy(),
        wind_df=wind_df.copy(),
        generators_df=generators_df.copy(),
        phase2_config=cfg,
    )


def run_phase2_relaxed_ramp(demand_df, solar_df, wind_df, generators_df) -> ScenarioResult:
    """Phase 2: Relaxed thermal ramp."""
    cfg = Phase2Config(
        enable_ramp=True,
        ramp_limit_mw_per_hour=400.0,
        initial_thermal_output_mw=400.0,
        enable_co2_cap=False,
        enable_battery=False,
    )
    return run_scenario(
        name="P2: Relaxed Ramp (400 MW/hr)",
        description="Relaxed ramp limits have less impact on dispatch than tight limits.",
        demand_df=demand_df.copy(),
        solar_df=solar_df.copy(),
        wind_df=wind_df.copy(),
        generators_df=generators_df.copy(),
        phase2_config=cfg,
    )


def run_phase2_battery_only(demand_df, solar_df, wind_df, generators_df) -> ScenarioResult:
    """Phase 2: Battery enabled, no CO2 cap or ramp — shows pure storage arbitrage."""
    cfg = Phase2Config(
        enable_ramp=False,
        enable_co2_cap=False,
        enable_battery=True,
        battery_capacity_mwh=400.0,
        charge_rate_max_mw=100.0,
        discharge_rate_max_mw=100.0,
        charge_efficiency=0.948,
        discharge_efficiency=0.948,
        initial_soc_mwh=0.0,
        min_soc_mwh=0.0,
        max_soc_mwh=400.0,
    )
    return run_scenario(
        name="P2: Battery Only",
        description="Battery enabled without ramp/CO2 constraints. May charge during solar peak and discharge at evening.",
        demand_df=demand_df.copy(),
        solar_df=solar_df.copy(),
        wind_df=wind_df.copy(),
        generators_df=generators_df.copy(),
        phase2_config=cfg,
    )
