"""
RenewOpt LP Optimizer — Phase 2 Extended Model.

Supports:
- Phase 1 baseline dispatch (solar/wind/thermal)
- Shadow prices / dual values from demand-balance constraints
- Thermal ramp-rate constraints (inter-temporal)
- Hourly CO2 emission caps
- Battery energy storage (charge/discharge/SOC)
- Reliability mode (optional unmet demand with penalty)
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
import pandas as pd
import numpy as np
import pulp
import warnings


@dataclass
class OptimizationResult:
    status: str                       # 'Optimal', 'Infeasible', 'Unbounded', 'Error'
    solver_status: str                # Raw PuLP status string
    total_cost: Optional[float]       # Objective value (None if not optimal)
    dispatch_df: Optional[pd.DataFrame]  # Hourly dispatch table
    message: str                      # Human-readable explanation
    objective_value: Optional[float]  # Same as total_cost, alias
    is_verified: bool = False         # Whether post-solve verification passed
    shadow_prices: Optional[Dict[int, float]] = None  # Dual values for demand balance
    total_unmet_demand: float = 0.0   # Total unmet demand (MWh)


@dataclass
class Phase2Config:
    """Configuration for Phase 2 advanced features."""
    # Thermal ramp
    enable_ramp: bool = False
    ramp_limit_mw_per_hour: float = 200.0
    initial_thermal_output_mw: float = 400.0

    # CO2 cap
    enable_co2_cap: bool = False
    co2_cap_df: Optional[pd.DataFrame] = None  # hour, co2_cap_kg

    # Battery
    enable_battery: bool = False
    battery_capacity_mwh: float = 400.0
    charge_rate_max_mw: float = 100.0
    discharge_rate_max_mw: float = 100.0
    charge_efficiency: float = 0.90
    discharge_efficiency: float = 0.90
    initial_soc_mwh: float = 200.0
    min_soc_mwh: float = 40.0
    max_soc_mwh: float = 360.0

    # Reliability mode
    enable_reliability: bool = False
    unmet_demand_penalty: float = 50000.0  # ₹/MWh — must be >> any generation cost


def solve_dispatch(
    demand_df: pd.DataFrame,
    solar_df: pd.DataFrame,
    wind_df: pd.DataFrame,
    generators_df: pd.DataFrame,
    phase2_config: Optional[Phase2Config] = None,
) -> OptimizationResult:
    """
    Solve the 24-hour electricity dispatch Linear Programming model.

    Phase 1 LP Formulation (always active):
        Decision Variables: S[t], W[t], T[t] for each hour t
        Objective: Minimize Σ(Cs·S[t] + Cw·W[t] + Cth·T[t])
        Constraints: demand balance, availability bounds, non-negativity

    Phase 2 Extensions (when enabled):
        Shadow Prices: extracted from demand-balance constraint duals
        Thermal Ramp: T[t] - T[t-1] ≤ RampLimit, T[t-1] - T[t] ≤ RampLimit
        CO2 Cap: T[t] · co2_per_mwh ≤ CO2Cap[t]
        Battery: C[t], D[t], SOC[t] with demand balance S+W+T+D-C = Demand
        Reliability: Unmet[t] with high penalty in objective
    """
    cfg = phase2_config or Phase2Config()

    # --- Extract generator parameters ---
    gen = generators_df.set_index("source")
    cost_solar = float(gen.loc["Solar", "cost_per_mwh"])
    cost_wind = float(gen.loc["Wind", "cost_per_mwh"])
    cost_thermal = float(gen.loc["Thermal", "cost_per_mwh"])
    thermal_capacity = float(gen.loc["Thermal", "max_capacity_mw"])
    co2_per_mwh_thermal = float(gen.loc["Thermal", "co2_per_mwh"])

    # --- Build hour-indexed lookup tables ---
    demand = demand_df.set_index("hour")["demand_mw"].to_dict()
    solar_avail = solar_df.set_index("hour")["solar_available_mw"].to_dict()
    wind_avail = wind_df.set_index("hour")["wind_available_mw"].to_dict()
    hours = sorted(demand.keys())

    # CO2 cap lookup
    co2_cap = {}
    if cfg.enable_co2_cap and cfg.co2_cap_df is not None:
        co2_cap = cfg.co2_cap_df.set_index("hour")["co2_cap_kg"].to_dict()

    # --- Create LP problem ---
    prob = pulp.LpProblem("RenewOpt_Dispatch", pulp.LpMinimize)

    # --- Decision variables ---
    S = {t: pulp.LpVariable(f"Solar_{t}", lowBound=0, upBound=solar_avail[t]) for t in hours}
    W = {t: pulp.LpVariable(f"Wind_{t}", lowBound=0, upBound=wind_avail[t]) for t in hours}
    T = {t: pulp.LpVariable(f"Thermal_{t}", lowBound=0, upBound=thermal_capacity) for t in hours}

    # Battery variables (only if enabled)
    C_bat = {}  # charge
    D_bat = {}  # discharge
    SOC = {}    # state of charge
    if cfg.enable_battery:
        for t in hours:
            C_bat[t] = pulp.LpVariable(f"Charge_{t}", lowBound=0, upBound=cfg.charge_rate_max_mw)
            D_bat[t] = pulp.LpVariable(f"Discharge_{t}", lowBound=0, upBound=cfg.discharge_rate_max_mw)
            SOC[t] = pulp.LpVariable(f"SOC_{t}", lowBound=cfg.min_soc_mwh, upBound=cfg.max_soc_mwh)

    # Unmet demand variables (only if reliability mode enabled)
    Unmet = {}
    if cfg.enable_reliability:
        for t in hours:
            Unmet[t] = pulp.LpVariable(f"Unmet_{t}", lowBound=0)

    # --- Objective function ---
    obj_terms = [
        cost_solar * S[t] + cost_wind * W[t] + cost_thermal * T[t]
        for t in hours
    ]
    if cfg.enable_reliability:
        obj_terms += [cfg.unmet_demand_penalty * Unmet[t] for t in hours]
    # Battery has no direct generation cost (stores/releases existing energy)

    prob += (pulp.lpSum(obj_terms), "Total_Generation_Cost")

    # --- Demand balance constraints ---
    demand_constraints = {}
    for t in hours:
        lhs = S[t] + W[t] + T[t]
        if cfg.enable_battery:
            lhs += D_bat[t] - C_bat[t]
        if cfg.enable_reliability:
            lhs += Unmet[t]
        constraint_name = f"Demand_Balance_Hour_{t}"
        prob += (lhs == demand[t], constraint_name)
        demand_constraints[t] = constraint_name

    # --- Thermal ramp constraints ---
    if cfg.enable_ramp:
        ramp_limit = cfg.ramp_limit_mw_per_hour
        initial_thermal = cfg.initial_thermal_output_mw
        for i, t in enumerate(hours):
            if i == 0:
                prev_val = initial_thermal
                prob += (T[t] - prev_val <= ramp_limit, f"Ramp_Up_Hour_{t}")
                prob += (prev_val - T[t] <= ramp_limit, f"Ramp_Down_Hour_{t}")
            else:
                t_prev = hours[i - 1]
                prob += (T[t] - T[t_prev] <= ramp_limit, f"Ramp_Up_Hour_{t}")
                prob += (T[t_prev] - T[t] <= ramp_limit, f"Ramp_Down_Hour_{t}")

    # --- Hourly CO2 cap constraints ---
    if cfg.enable_co2_cap and co2_cap:
        for t in hours:
            if t in co2_cap:
                prob += (
                    T[t] * co2_per_mwh_thermal <= co2_cap[t],
                    f"CO2_Cap_Hour_{t}",
                )

    # --- Battery SOC dynamics ---
    if cfg.enable_battery:
        eta_c = cfg.charge_efficiency
        eta_d = cfg.discharge_efficiency
        for i, t in enumerate(hours):
            if i == 0:
                prob += (
                    SOC[t] == cfg.initial_soc_mwh + eta_c * C_bat[t] - D_bat[t] / eta_d,
                    f"SOC_Dynamics_Hour_{t}",
                )
            else:
                t_prev = hours[i - 1]
                prob += (
                    SOC[t] == SOC[t_prev] + eta_c * C_bat[t] - D_bat[t] / eta_d,
                    f"SOC_Dynamics_Hour_{t}",
                )

    # --- Solve ---
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        solver = pulp.PULP_CBC_CMD(msg=0)
        prob.solve(solver)

    # --- Interpret solver status ---
    solver_status = pulp.LpStatus[prob.status]

    if prob.status != 1:  # Not Optimal
        status_map = {-1: "Infeasible", -2: "Unbounded"}
        status = status_map.get(prob.status, "Error")
        msg_map = {
            -1: "The LP is infeasible. Demand cannot be satisfied given current constraints.",
            -2: "The LP is unbounded. Check model formulation.",
        }
        message = msg_map.get(prob.status, f"Solver returned unexpected status: {solver_status}")
        return OptimizationResult(
            status=status,
            solver_status=solver_status,
            total_cost=None,
            dispatch_df=None,
            message=message,
            objective_value=None,
        )

    status = "Optimal"
    message = "Optimal solution found. All constraints satisfied."

    # --- Extract shadow prices from demand-balance constraints ---
    shadow_prices = {}
    for t in hours:
        cname = demand_constraints[t]
        constraint = prob.constraints.get(cname)
        if constraint is not None:
            shadow_prices[t] = constraint.pi if constraint.pi is not None else 0.0
        else:
            shadow_prices[t] = 0.0

    # --- Extract optimal values ---
    objective_value = pulp.value(prob.objective)

    records = []
    for t in hours:
        s_val = pulp.value(S[t]) or 0.0
        w_val = pulp.value(W[t]) or 0.0
        th_val = pulp.value(T[t]) or 0.0

        charge_val = pulp.value(C_bat[t]) or 0.0 if cfg.enable_battery else 0.0
        discharge_val = pulp.value(D_bat[t]) or 0.0 if cfg.enable_battery else 0.0
        soc_val = pulp.value(SOC[t]) or 0.0 if cfg.enable_battery else 0.0
        unmet_val = pulp.value(Unmet[t]) or 0.0 if cfg.enable_reliability else 0.0

        total_gen = s_val + w_val + th_val + discharge_val - charge_val + unmet_val
        records.append({
            "hour": t,
            "demand_mw": demand[t],
            "solar_mw": s_val,
            "wind_mw": w_val,
            "thermal_mw": th_val,
            "total_generation_mw": s_val + w_val + th_val,
            "solar_cost": cost_solar * s_val,
            "wind_cost": cost_wind * w_val,
            "thermal_cost": cost_thermal * th_val,
            "hour_total_cost": cost_solar * s_val + cost_wind * w_val + cost_thermal * th_val,
            "charge_mw": charge_val,
            "discharge_mw": discharge_val,
            "soc_mwh": soc_val,
            "unmet_mw": unmet_val,
            "shadow_price": shadow_prices.get(t, 0.0),
            "thermal_co2_kg": th_val * co2_per_mwh_thermal,
        })

    dispatch_df = pd.DataFrame(records)

    total_unmet = dispatch_df["unmet_mw"].sum() if cfg.enable_reliability else 0.0

    # --- Post-solve verification ---
    is_verified, verification_notes = _verify_solution(
        dispatch_df, demand, solar_avail, wind_avail, thermal_capacity,
        objective_value, cfg, co2_cap, co2_per_mwh_thermal
    )

    if not is_verified:
        message = f"WARNING: Solution verification failed. {verification_notes}"
        status = "Error"

    result = OptimizationResult(
        status=status,
        solver_status=solver_status,
        total_cost=objective_value,
        dispatch_df=dispatch_df,
        message=message,
        objective_value=objective_value,
        is_verified=is_verified,
        shadow_prices=shadow_prices,
        total_unmet_demand=total_unmet,
    )
    return result


def _verify_solution(dispatch_df, demand, solar_avail, wind_avail, thermal_capacity,
                     objective_value, cfg, co2_cap, co2_per_mwh_thermal, tol=1e-4):
    """
    Verify that the optimal dispatch satisfies all model constraints.
    Returns (bool, notes_string).
    """
    notes = []
    hours = sorted(demand.keys())

    for _, row in dispatch_df.iterrows():
        t = int(row["hour"])

        # Demand balance (including battery and unmet)
        gen_total = row["solar_mw"] + row["wind_mw"] + row["thermal_mw"]
        net_gen = gen_total + row.get("discharge_mw", 0.0) - row.get("charge_mw", 0.0) + row.get("unmet_mw", 0.0)
        if abs(net_gen - demand[t]) > tol:
            notes.append(f"Hour {t}: demand balance violated (net_gen={net_gen:.3f}, demand={demand[t]:.3f})")

        # Non-negativity
        if row["solar_mw"] < -tol:
            notes.append(f"Hour {t}: solar generation negative ({row['solar_mw']:.4f})")
        if row["wind_mw"] < -tol:
            notes.append(f"Hour {t}: wind generation negative ({row['wind_mw']:.4f})")
        if row["thermal_mw"] < -tol:
            notes.append(f"Hour {t}: thermal generation negative ({row['thermal_mw']:.4f})")

        # Availability
        if row["solar_mw"] > solar_avail[t] + tol:
            notes.append(f"Hour {t}: solar exceeds availability ({row['solar_mw']:.3f} > {solar_avail[t]:.3f})")
        if row["wind_mw"] > wind_avail[t] + tol:
            notes.append(f"Hour {t}: wind exceeds availability ({row['wind_mw']:.3f} > {wind_avail[t]:.3f})")
        if row["thermal_mw"] > thermal_capacity + tol:
            notes.append(f"Hour {t}: thermal exceeds capacity ({row['thermal_mw']:.3f} > {thermal_capacity:.3f})")

        # CO2 cap
        if cfg.enable_co2_cap and co2_cap and t in co2_cap:
            actual_co2 = row["thermal_mw"] * co2_per_mwh_thermal
            if actual_co2 > co2_cap[t] + 1.0:  # Use 1.0 kg tolerance
                notes.append(f"Hour {t}: CO2 cap violated ({actual_co2:.1f} > {co2_cap[t]:.1f})")

        # Battery bounds
        if cfg.enable_battery:
            if row.get("charge_mw", 0) < -tol:
                notes.append(f"Hour {t}: charge negative ({row['charge_mw']:.4f})")
            if row.get("discharge_mw", 0) < -tol:
                notes.append(f"Hour {t}: discharge negative ({row['discharge_mw']:.4f})")
            if row.get("charge_mw", 0) > cfg.charge_rate_max_mw + tol:
                notes.append(f"Hour {t}: charge exceeds limit ({row['charge_mw']:.3f} > {cfg.charge_rate_max_mw})")
            if row.get("discharge_mw", 0) > cfg.discharge_rate_max_mw + tol:
                notes.append(f"Hour {t}: discharge exceeds limit ({row['discharge_mw']:.3f} > {cfg.discharge_rate_max_mw})")
            if row.get("soc_mwh", 0) < cfg.min_soc_mwh - tol:
                notes.append(f"Hour {t}: SOC below min ({row['soc_mwh']:.3f} < {cfg.min_soc_mwh})")
            if row.get("soc_mwh", 0) > cfg.max_soc_mwh + tol:
                notes.append(f"Hour {t}: SOC above max ({row['soc_mwh']:.3f} > {cfg.max_soc_mwh})")

    # Thermal ramp verification
    if cfg.enable_ramp:
        ramp_limit = cfg.ramp_limit_mw_per_hour
        initial_thermal = cfg.initial_thermal_output_mw
        thermal_vals = dispatch_df.sort_values("hour")["thermal_mw"].tolist()
        for i, t in enumerate(hours):
            if i == 0:
                ramp = abs(thermal_vals[i] - initial_thermal)
            else:
                ramp = abs(thermal_vals[i] - thermal_vals[i - 1])
            if ramp > ramp_limit + tol:
                notes.append(f"Hour {t}: ramp violation ({ramp:.3f} > {ramp_limit})")

    # Battery SOC dynamics verification
    if cfg.enable_battery:
        sorted_df = dispatch_df.sort_values("hour")
        eta_c = cfg.charge_efficiency
        eta_d = cfg.discharge_efficiency
        prev_soc = cfg.initial_soc_mwh
        for _, row in sorted_df.iterrows():
            t = int(row["hour"])
            expected_soc = prev_soc + eta_c * row["charge_mw"] - row["discharge_mw"] / eta_d
            if abs(row["soc_mwh"] - expected_soc) > tol:
                notes.append(f"Hour {t}: SOC dynamics error (actual={row['soc_mwh']:.3f}, expected={expected_soc:.3f})")
            prev_soc = row["soc_mwh"]

    # Cost verification
    cost_sum = dispatch_df["hour_total_cost"].sum()
    if cfg.enable_reliability:
        cost_sum += dispatch_df["unmet_mw"].sum() * cfg.unmet_demand_penalty
    if abs(cost_sum - objective_value) > 1.0:
        notes.append(f"Cost mismatch: sum={cost_sum:.2f}, objective={objective_value:.2f}")

    is_verified = len(notes) == 0
    return is_verified, "; ".join(notes) if notes else "All checks passed."
