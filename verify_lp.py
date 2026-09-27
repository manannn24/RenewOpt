"""
LP Verification Script for RenewOpt.
Runs the optimizer on default data and verifies all constraints and metrics.
"""
from src.data_loader import load_default_data
from src.optimizer import solve_dispatch
from src.calculations import build_metrics
from src.validation import validate_data, check_feasibility
from src.scenarios import run_all_scenarios

print("=" * 60)
print("RENEWOPT LP VERIFICATION SCRIPT")
print("=" * 60)

# ── 1. Load data ──────────────────────────────────────────────
b = load_default_data()
print("\n[1] DATASET LOADED")
print(f"  Demand rows: {len(b.demand_df)}")
print(f"  Solar rows:  {len(b.solar_df)}")
print(f"  Wind rows:   {len(b.wind_df)}")
print(f"  Generators:  {list(b.generators_df['source'])}")

# ── 2. Validation ─────────────────────────────────────────────
vr = validate_data(b.demand_df, b.solar_df, b.wind_df, b.generators_df)
print(f"\n[2] VALIDATION: {'PASS' if vr.is_valid else 'FAIL'}")
if not vr.is_valid:
    for e in vr.errors:
        print(f"    ERROR: {e}")

# ── 3. Feasibility ────────────────────────────────────────────
inf_hours = check_feasibility(b.demand_df, b.solar_df, b.wind_df, b.generators_df)
print(f"\n[3] PRE-FEASIBILITY: {len(inf_hours)} infeasible hours (expect 0)")
if inf_hours:
    for h in inf_hours:
        print(f"    Hour {h['hour']}: demand={h['demand']}, max_avail={h['max_available']:.1f}, shortfall={h['shortfall']:.1f}")

# ── 4. Optimization ───────────────────────────────────────────
print("\n[4] LP OPTIMIZATION (CBC solver)")
result = solve_dispatch(b.demand_df, b.solar_df, b.wind_df, b.generators_df)
print(f"  Status:       {result.status}")
print(f"  Solver:       {result.solver_status}")
print(f"  Verified:     {result.is_verified}")
print(f"  Total cost:   {result.total_cost:,.2f}")

# ── 5. Metrics ────────────────────────────────────────────────
m = build_metrics(result.dispatch_df, b.generators_df)
print("\n[5] METRICS")
print(f"  Total demand:        {m['total_demand_mwh']:,.0f} MWh")
print(f"  Total generation:    {m['total_generation_mwh']:,.0f} MWh")
print(f"  Renewable gen:       {m['renewable_generation_mwh']:,.0f} MWh")
print(f"  Renewable share:     {m['renewable_share_pct']:.2f}%")
print(f"  Thermal dependency:  {m['thermal_dependency_pct']:.2f}%")
print(f"  Total cost:          {m['total_cost']:,.2f}")
print(f"    Solar cost:        {m['solar_cost']:,.2f}")
print(f"    Wind cost:         {m['wind_cost']:,.2f}")
print(f"    Thermal cost:      {m['thermal_cost']:,.2f}")
print(f"  CO2 total:           {m['total_kg_co2']:,.0f} kg")
print(f"    Solar CO2:         {m['solar_kg_co2']:,.0f} kg")
print(f"    Wind CO2:          {m['wind_kg_co2']:,.0f} kg")
print(f"    Thermal CO2:       {m['thermal_kg_co2']:,.0f} kg")

# ── 6. Constraint Verification ────────────────────────────────
df = result.dispatch_df
max_balance_err = (df['solar_mw'] + df['wind_mw'] + df['thermal_mw'] - df['demand_mw']).abs().max()
print("\n[6] CONSTRAINT VERIFICATION")
print(f"  Max demand balance error: {max_balance_err:.10f} (must be < 0.001)")
print(f"  Max solar dispatch:       {df['solar_mw'].max():.4f} MW  (avail max: 400.0)")
print(f"  Max wind dispatch:        {df['wind_mw'].max():.4f} MW  (avail max: 300.0)")
print(f"  Max thermal dispatch:     {df['thermal_mw'].max():.4f} MW  (capacity: 800.0)")
print(f"  Min solar:                {df['solar_mw'].min():.8f} MW (must be >= 0)")
print(f"  Min wind:                 {df['wind_mw'].min():.8f} MW (must be >= 0)")
print(f"  Min thermal:              {df['thermal_mw'].min():.8f} MW (must be >= 0)")

# Verify cost matches objective
cost_from_cols = df['solar_cost'].sum() + df['wind_cost'].sum() + df['thermal_cost'].sum()
cost_diff = abs(cost_from_cols - result.total_cost)
print(f"  Cost column sum:          {cost_from_cols:,.2f}")
print(f"  Objective value:          {result.total_cost:,.2f}")
print(f"  Cost match error:         {cost_diff:.6f} (must be < 1.0)")

# ── 7. Dispatch Table ─────────────────────────────────────────
print("\n[7] OPTIMAL DISPATCH TABLE")
print(f"{'Hour':>4} {'Demand':>8} {'Solar':>8} {'Wind':>8} {'Thermal':>9} {'Total':>8}")
print("-" * 52)
for _, row in df.iterrows():
    print(f"  {int(row['hour']):2d}   {row['demand_mw']:7.1f}  {row['solar_mw']:7.1f}  {row['wind_mw']:7.1f}  {row['thermal_mw']:8.1f}  {row['total_generation_mw']:7.1f}")

# ── 8. Scenario Analysis Verification ────────────────────────
print("\n[8] SCENARIO ANALYSIS")
scenarios = run_all_scenarios(b.demand_df, b.solar_df, b.wind_df, b.generators_df)
for name, sr in scenarios.items():
    if sr.status == "Optimal":
        m2 = sr.metrics
        print(f"  {name:35s}: OPTIMAL  cost={m2['total_cost']:>10,.0f}  ren={m2['renewable_share_pct']:.1f}%  CO2={m2['total_kg_co2']:>10,.0f} kg")
    else:
        print(f"  {name:35s}: {sr.status}")

# ── 9. Infeasible Case ────────────────────────────────────────
import pandas as pd
print("\n[9] INFEASIBLE CASE TEST")
infeasible_demand = pd.DataFrame({"hour": [0], "demand_mw": [10000.0]})
inf_result = solve_dispatch(
    infeasible_demand,
    pd.DataFrame({"hour": [0], "solar_available_mw": [100.0]}),
    pd.DataFrame({"hour": [0], "wind_available_mw": [100.0]}),
    pd.DataFrame({
        "source": ["Solar", "Wind", "Thermal"],
        "max_capacity_mw": [100.0, 100.0, 100.0],
        "cost_per_mwh": [10.0, 15.0, 85.0],
        "co2_per_mwh": [0.0, 0.0, 820.0],
    }),
)
print(f"  Infeasible case status: {inf_result.status} (expect: Infeasible)")
print(f"  dispatch_df is None:    {inf_result.dispatch_df is None} (expect: True)")
print(f"  total_cost is None:     {inf_result.total_cost is None} (expect: True)")

print("\n" + "=" * 60)
print("PHASE 2 VERIFICATION")
print("=" * 60)

from src.scenarios import (
    run_phase2_extended_baseline,
    run_phase2_tight_co2,
    run_phase2_co2_with_battery,
    run_phase2_insufficient_battery,
    run_phase2_tight_ramp,
    run_phase2_relaxed_ramp,
    run_phase2_battery_only,
)

print("\n[10] PHASE 2 SCENARIOS")
p2_scenarios = {
    "P2 Baseline": run_phase2_extended_baseline(b.demand_df, b.solar_df, b.wind_df, b.generators_df, b.co2_cap_df),
    "P2 Tight CO2 (No Batt)": run_phase2_tight_co2(b.demand_df, b.solar_df, b.wind_df, b.generators_df, b.co2_cap_df),
    "P2 Tight CO2 + Battery": run_phase2_co2_with_battery(b.demand_df, b.solar_df, b.wind_df, b.generators_df, b.co2_cap_df),
    "P2 Insuff. Battery": run_phase2_insufficient_battery(b.demand_df, b.solar_df, b.wind_df, b.generators_df, b.co2_cap_df),
    "P2 Tight Ramp": run_phase2_tight_ramp(b.demand_df, b.solar_df, b.wind_df, b.generators_df),
    "P2 Relaxed Ramp": run_phase2_relaxed_ramp(b.demand_df, b.solar_df, b.wind_df, b.generators_df),
    "P2 Battery Only": run_phase2_battery_only(b.demand_df, b.solar_df, b.wind_df, b.generators_df),
}

for name, sr in p2_scenarios.items():
    if sr.status == "Optimal":
        m2 = sr.metrics
        unmet = m2.get('total_unmet_mwh', 0.0)
        unmet_str = f" unmet={unmet:.1f}" if unmet > 0 else ""
        print(f"  {name:25s}: OPTIMAL  cost={m2['total_cost']:>10,.0f}  CO2={m2['total_kg_co2']:>10,.0f}{unmet_str}")
    else:
        print(f"  {name:25s}: {sr.status}")

print("\n" + "=" * 60)
print("PHASE 2 8760-HOUR VERIFICATION")
print("=" * 60)

from src.data_loader import load_8760_data
print("\n[11] LOADING 8760 DATASET")
b_8760 = load_8760_data()
print(f"  Demand rows: {len(b_8760.demand_df)}")
print(f"  Solar rows:  {len(b_8760.solar_df)}")
print(f"  Wind rows:   {len(b_8760.wind_df)}")
assert len(b_8760.demand_df) == 8760, "Must be exactly 8760 rows"

print("\n[12] SOLVING 8760 BASELINE SCENARIO")
# The 8760 optimization might take some time, so we just test the baseline
from src.scenarios import run_baseline
sr_8760 = run_baseline(b_8760.demand_df, b_8760.solar_df, b_8760.wind_df, b_8760.generators_df)
print(f"  Status:       {sr_8760.status}")
if sr_8760.status == "Optimal":
    m_8760 = sr_8760.metrics
    print(f"  Total cost:   {m_8760['total_cost']:,.0f}")
    print(f"  CO2 total:    {m_8760['total_kg_co2']:,.0f} kg")
    print(f"  Ren Share:    {m_8760['renewable_share_pct']:.2f}%")

print("\n" + "=" * 60)
print("ALL VERIFICATION COMPLETE")
print("=" * 60)
