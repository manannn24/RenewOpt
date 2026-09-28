import pandas as pd
from typing import Dict, List, Optional
from src.optimizer import solve_dispatch, Phase2Config
from src.data_loader import DataBundle

def diagnose_infeasibility(
    demand_df: pd.DataFrame,
    solar_df: pd.DataFrame,
    wind_df: pd.DataFrame,
    generators_df: pd.DataFrame,
    failed_cfg: Phase2Config
) -> Optional[Dict]:
    """
    If a strict LP is infeasible, this runs a relaxed version (with reliability mode)
    to pinpoint exactly which hour transitions caused the infeasibility.
    Returns a dictionary with diagnostic details.
    """
    if failed_cfg.enable_reliability:
        return None  # If reliability was already on, it shouldn't be infeasible unless data is severely corrupted.

    # 1. Run with reliability mode enabled to identify bottleneck hours
    # We copy the config and force reliability on.
    import copy
    rel_cfg = copy.deepcopy(failed_cfg)
    rel_cfg.enable_reliability = True
    
    res = solve_dispatch(demand_df, solar_df, wind_df, generators_df, rel_cfg)
    if res.status != "Optimal":
        return None  # Couldn't even solve with reliability on

    disp = res.dispatch_df
    if disp is None:
        return None

    unmet = disp[disp["unmet_mw"] > 1e-4]
    if unmet.empty:
        # It's feasible with reliability, but unmet is 0? 
        # This implies numeric tolerance differences or marginal infeasibility.
        return {"reason": "marginal"}
    
    # 2. Extract the most restrictive hour
    # We'll take the first hour with unmet demand as the primary critical hour
    critical_row = unmet.iloc[0]
    t = int(critical_row["hour"])
    t_prev = t - 1 if t > 0 else None
    
    diag = {
        "critical_hour": t,
        "demand": critical_row["demand_mw"],
        "unmet_mw": critical_row["unmet_mw"],
        "thermal_mw": critical_row["thermal_mw"],
        "solar_mw": critical_row["solar_mw"],
        "wind_mw": critical_row["wind_mw"],
        "battery_available": failed_cfg.enable_battery,
        "would_reliability_resolve": True,
        "ramp_limit_mw": failed_cfg.ramp_limit_mw_per_hour if failed_cfg.enable_ramp else None,
        "initial_thermal_mw": failed_cfg.initial_thermal_output_mw if failed_cfg.enable_ramp else None
    }
    
    if failed_cfg.enable_battery:
        diag["battery_discharge_mw"] = critical_row.get("discharge_mw", 0.0)
        diag["battery_charge_mw"] = critical_row.get("charge_mw", 0.0)
        diag["battery_soc_mwh"] = critical_row.get("soc_mwh", 0.0)
        
    if t_prev is not None:
        prev_row = disp[disp["hour"] == t_prev].iloc[0]
        diag["prev_thermal_mw"] = prev_row["thermal_mw"]
        diag["thermal_change_mw"] = critical_row["thermal_mw"] - prev_row["thermal_mw"]
    else:
        diag["prev_thermal_mw"] = failed_cfg.initial_thermal_output_mw
        diag["thermal_change_mw"] = critical_row["thermal_mw"] - failed_cfg.initial_thermal_output_mw

    return diag
