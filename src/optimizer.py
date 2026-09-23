from dataclasses import dataclass
from typing import Optional
import pandas as pd
import pulp

@dataclass
class OptimizationResult:
    status: str                       # 'Optimal', 'Infeasible', 'Unbounded', 'Error'
    solver_status: str                # Raw PuLP status string
    total_cost: Optional[float]       # Objective value (None if not optimal)
    dispatch_df: Optional[pd.DataFrame]  # Hourly dispatch table
    message: str                      # Human-readable explanation
    objective_value: Optional[float]  # Same as total_cost, alias
    is_verified: bool = False         # Whether post-solve verification passed


def solve_dispatch(
    demand_df: pd.DataFrame,
    solar_df: pd.DataFrame,
    wind_df: pd.DataFrame,
    generators_df: pd.DataFrame,
) -> OptimizationResult:
    """
    Solve the 24-hour electricity dispatch Linear Programming model.

    LP Formulation
    --------------
    Decision Variables:
        S[t] = solar generation at hour t   (MWh, continuous, >= 0)
        W[t] = wind generation at hour t    (MWh, continuous, >= 0)
        T[t] = thermal generation at hour t (MWh, continuous, >= 0)

    Objective (Minimize):
        Z = sum_t ( cost_solar * S[t] + cost_wind * W[t] + cost_thermal * T[t] )

    Constraints:
        For each hour t:
            S[t] + W[t] + T[t] == demand[t]       (demand balance)
            S[t] <= solar_available[t]             (solar availability)
            W[t] <= wind_available[t]              (wind availability)
            T[t] <= thermal_capacity               (thermal capacity)
            S[t], W[t], T[t] >= 0                 (non-negativity, via lowBound=0)
    """
    # --- Extract generator parameters ---
    gen = generators_df.set_index("source")
    cost_solar = float(gen.loc["Solar", "cost_per_mwh"])
    cost_wind = float(gen.loc["Wind", "cost_per_mwh"])
    cost_thermal = float(gen.loc["Thermal", "cost_per_mwh"])
    thermal_capacity = float(gen.loc["Thermal", "max_capacity_mw"])

    # --- Build hour-indexed lookup tables ---
    demand = demand_df.set_index("hour")["demand_mw"].to_dict()
    solar_avail = solar_df.set_index("hour")["solar_available_mw"].to_dict()
    wind_avail = wind_df.set_index("hour")["wind_available_mw"].to_dict()
    hours = sorted(demand.keys())

    # --- Create LP problem ---
    prob = pulp.LpProblem("RenewOpt_Dispatch", pulp.LpMinimize)

    # --- Decision variables ---
    # S[t]: solar generation at hour t
    S = {t: pulp.LpVariable(f"Solar_{t}", lowBound=0, upBound=solar_avail[t]) for t in hours}
    # W[t]: wind generation at hour t
    W = {t: pulp.LpVariable(f"Wind_{t}", lowBound=0, upBound=wind_avail[t]) for t in hours}
    # T[t]: thermal generation at hour t
    T = {t: pulp.LpVariable(f"Thermal_{t}", lowBound=0, upBound=thermal_capacity) for t in hours}

    # --- Objective function ---
    # Minimize total generation cost
    prob += (
        pulp.lpSum(
            cost_solar * S[t] + cost_wind * W[t] + cost_thermal * T[t]
            for t in hours
        ),
        "Total_Generation_Cost",
    )

    # --- Constraints ---
    for t in hours:
        # Demand balance (equality constraint)
        prob += (
            S[t] + W[t] + T[t] == demand[t],
            f"Demand_Balance_Hour_{t}",
        )
        # Solar availability (upper bound - already set via upBound, but explicit constraint improves readability)
        # Note: upBound on LpVariable implements this; explicit constraint redundant but shows model transparency
        # Wind availability - same note
        # Thermal capacity - same note
        # Non-negativity: enforced by lowBound=0 on all variables

    # --- Solve ---
    # Use the bundled CBC solver included with PuLP (PULP_CBC_CMD).
    # DeprecationWarning is suppressed since CBC comes bundled with pulp package.
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        solver = pulp.PULP_CBC_CMD(msg=0)
        prob.solve(solver)

    # --- Interpret solver status ---
    solver_status = pulp.LpStatus[prob.status]

    if prob.status == 1:  # Optimal
        status = "Optimal"
        message = "Optimal solution found. All constraints satisfied."
    elif prob.status == -1:  # Infeasible
        status = "Infeasible"
        message = "The LP is infeasible. Demand cannot be satisfied given current constraints."
        return OptimizationResult(
            status=status,
            solver_status=solver_status,
            total_cost=None,
            dispatch_df=None,
            message=message,
            objective_value=None,
        )
    elif prob.status == -2:  # Unbounded
        status = "Unbounded"
        message = "The LP is unbounded. Check model formulation."
        return OptimizationResult(
            status=status,
            solver_status=solver_status,
            total_cost=None,
            dispatch_df=None,
            message=message,
            objective_value=None,
        )
    else:
        status = "Error"
        message = f"Solver returned unexpected status: {solver_status}"
        return OptimizationResult(
            status=status,
            solver_status=solver_status,
            total_cost=None,
            dispatch_df=None,
            message=message,
            objective_value=None,
        )

    # --- Extract optimal values ---
    objective_value = pulp.value(prob.objective)

    records = []
    for t in hours:
        s_val = pulp.value(S[t]) or 0.0
        w_val = pulp.value(W[t]) or 0.0
        th_val = pulp.value(T[t]) or 0.0
        total_gen = s_val + w_val + th_val
        records.append({
            "hour": t,
            "demand_mw": demand[t],
            "solar_mw": s_val,
            "wind_mw": w_val,
            "thermal_mw": th_val,
            "total_generation_mw": total_gen,
            "solar_cost": cost_solar * s_val,
            "wind_cost": cost_wind * w_val,
            "thermal_cost": cost_thermal * th_val,
            "hour_total_cost": cost_solar * s_val + cost_wind * w_val + cost_thermal * th_val,
        })

    dispatch_df = pd.DataFrame(records)

    # --- Post-solve verification ---
    is_verified, verification_notes = _verify_solution(
        dispatch_df, demand, solar_avail, wind_avail, thermal_capacity, objective_value
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
    )
    return result


def _verify_solution(dispatch_df, demand, solar_avail, wind_avail, thermal_capacity, objective_value, tol=1e-4):
    """
    Verify that the optimal dispatch satisfies all model constraints.
    Returns (bool, notes_string).
    """
    notes = []

    for _, row in dispatch_df.iterrows():
        t = int(row["hour"])

        # Demand balance
        gen_total = row["solar_mw"] + row["wind_mw"] + row["thermal_mw"]
        if abs(gen_total - demand[t]) > tol:
            notes.append(f"Hour {t}: demand balance violated (gen={gen_total:.3f}, demand={demand[t]:.3f})")

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

    # Cost verification
    cost_sum = dispatch_df["hour_total_cost"].sum()
    if abs(cost_sum - objective_value) > 1.0:  # Allow $1 tolerance for float arithmetic
        notes.append(f"Cost mismatch: sum={cost_sum:.2f}, objective={objective_value:.2f}")

    is_verified = len(notes) == 0
    return is_verified, "; ".join(notes) if notes else "All checks passed."
