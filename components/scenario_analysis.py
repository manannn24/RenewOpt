import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.scenarios import (
    run_baseline,
    run_high_demand,
    run_low_solar,
    run_high_thermal_cost,
    run_increased_renewable_capacity,
    run_phase2_extended_baseline,
    run_phase2_tight_co2,
    run_phase2_co2_with_battery,
    run_phase2_insufficient_battery,
    run_phase2_tight_ramp,
    run_phase2_relaxed_ramp,
    run_phase2_battery_only,
)

def render_scenario_analysis(demand_df, solar_df, wind_df, generators_df, co2_cap_df=None):
    """Render the Scenario Analysis page."""
    st.header("🔄 Scenario Analysis")
    st.markdown("Compare different operating conditions by re-running the LP optimizer with modified inputs.")

    scenario_map = {
        "Phase 1: Baseline": "Baseline",
        "Phase 1: High Demand (+20%)": "High Demand",
        "Phase 1: Low Solar (-50%)": "Low Solar",
        "Phase 1: High Thermal Cost (+30%)": "High Thermal Cost",
        "Phase 1: Increased Renewable Capacity (+200 MW Solar)": "Increased Renewable Capacity",
        "Phase 2: Extended Baseline (Ramp)": "P2 Baseline",
        "Phase 2: Tight CO2 (No Battery)": "P2 Tight CO2 (No Batt)",
        "Phase 2: Tight CO2 + Battery": "P2 Tight CO2 + Battery",
        "Phase 2: Insufficient Battery": "P2 Insuff. Battery",
        "Phase 2: Tight Ramp (80 MW/hr)": "P2 Tight Ramp",
        "Phase 2: Relaxed Ramp (400 MW/hr)": "P2 Relaxed Ramp",
        "Phase 2: Battery Arbitrage": "P2 Battery Only",
    }

    selected_scenarios = st.multiselect(
        "Select scenarios to run:",
        list(scenario_map.keys()),
        default=["Phase 1: Baseline", "Phase 2: Tight CO2 + Battery", "Phase 2: Insufficient Battery"],
    )

    if not selected_scenarios:
        st.info("Select at least one scenario.")
        return

    if st.button("▶️ Run Selected Scenarios", type="primary"):
        results = {}
        with st.spinner("Running scenario optimizations..."):
            for label in selected_scenarios:
                key = scenario_map[label]
                if key == "Baseline":
                    results[label] = run_baseline(demand_df, solar_df, wind_df, generators_df)
                elif key == "High Demand":
                    results[label] = run_high_demand(demand_df, solar_df, wind_df, generators_df, 1.20)
                elif key == "Low Solar":
                    results[label] = run_low_solar(demand_df, solar_df, wind_df, generators_df, 0.50)
                elif key == "High Thermal Cost":
                    results[label] = run_high_thermal_cost(demand_df, solar_df, wind_df, generators_df, 1.30)
                elif key == "Increased Renewable Capacity":
                    results[label] = run_increased_renewable_capacity(demand_df, solar_df, wind_df, generators_df, 200.0)
                elif key == "P2 Baseline":
                    results[label] = run_phase2_extended_baseline(demand_df, solar_df, wind_df, generators_df, co2_cap_df)
                elif key == "P2 Tight CO2 (No Batt)":
                    results[label] = run_phase2_tight_co2(demand_df, solar_df, wind_df, generators_df, co2_cap_df)
                elif key == "P2 Tight CO2 + Battery":
                    results[label] = run_phase2_co2_with_battery(demand_df, solar_df, wind_df, generators_df, co2_cap_df)
                elif key == "P2 Insuff. Battery":
                    results[label] = run_phase2_insufficient_battery(demand_df, solar_df, wind_df, generators_df, co2_cap_df)
                elif key == "P2 Tight Ramp":
                    results[label] = run_phase2_tight_ramp(demand_df, solar_df, wind_df, generators_df)
                elif key == "P2 Relaxed Ramp":
                    results[label] = run_phase2_relaxed_ramp(demand_df, solar_df, wind_df, generators_df)
                elif key == "P2 Battery Only":
                    results[label] = run_phase2_battery_only(demand_df, solar_df, wind_df, generators_df)
        st.session_state.scenario_results = results

    results = st.session_state.scenario_results
    if results:
        # --- Summary comparison table ---
        st.subheader("📋 Scenario Comparison Table")
        rows = []
        for label, sr in results.items():
            if sr.status == "Optimal" and sr.metrics:
                m = sr.metrics
                rows.append({
                    "Scenario": label,
                    "Status": "✅ Optimal",
                    "Total Cost (₹)": f"{m['total_cost']:,.0f}",
                    "Renewable Share (%)": f"{m['renewable_share_pct']:.1f}",
                    "CO₂ Emissions (kg)": f"{m['total_kg_co2']:,.0f}",
                    "Unmet Demand (MWh)": f"{m.get('total_unmet_mwh', 0.0):,.1f}",
                    "Peak SOC (MWh)": f"{m.get('peak_soc_mwh', 0.0):,.1f}" if "peak_soc_mwh" in m else "N/A",
                })
            else:
                rows.append({
                    "Scenario": label,
                    "Status": f"❌ {sr.status}",
                    "Total Cost (₹)": "N/A",
                    "Renewable Share (%)": "N/A",
                    "CO₂ Emissions (kg)": "N/A",
                    "Unmet Demand (MWh)": "N/A",
                    "Peak SOC (MWh)": "N/A",
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # --- Comparative bar charts ---
        optimal_results = {k: v for k, v in results.items() if v.status == "Optimal" and v.metrics}
        if len(optimal_results) >= 2:
            st.subheader("📊 Comparative Charts")
            
            col_a, col_b = st.columns(2)
            cost_data = {k: v.metrics["total_cost"] for k, v in optimal_results.items()}
            fig_cost = px.bar(x=list(cost_data.keys()), y=list(cost_data.values()), title="Total Cost", labels={"x": "", "y": "₹"}, color=list(cost_data.keys()))
            col_a.plotly_chart(fig_cost, use_container_width=True)

            co2_data = {k: v.metrics["total_kg_co2"] for k, v in optimal_results.items()}
            fig_co2 = px.bar(x=list(co2_data.keys()), y=list(co2_data.values()), title="CO₂ Emissions", labels={"x": "", "y": "kg"}, color=list(co2_data.keys()))
            col_b.plotly_chart(fig_co2, use_container_width=True)

        # Show dispatch comparison
        if optimal_results:
            st.subheader("🗓️ Hourly Dispatch Comparison")
            selected_for_dispatch = st.selectbox("View dispatch for scenario:", list(optimal_results.keys()))
            sr = optimal_results[selected_for_dispatch]
            df = sr.result.dispatch_df
            
            x_col = df["timestamp"] if "timestamp" in df.columns else df["hour"]
            x_title = "Time" if "timestamp" in df.columns else "Hour"
            
            fig_disp = go.Figure()
            fig_disp.add_trace(go.Scatter(x=x_col, y=df["solar_mw"], name="Solar", stackgroup='one', fillcolor="#FFA500", line=dict(width=0)))
            fig_disp.add_trace(go.Scatter(x=x_col, y=df["wind_mw"], name="Wind", stackgroup='one', fillcolor="#1E90FF", line=dict(width=0)))
            fig_disp.add_trace(go.Scatter(x=x_col, y=df["thermal_mw"], name="Thermal", stackgroup='one', fillcolor="#808080", line=dict(width=0)))
            if "discharge_mw" in df.columns:
                fig_disp.add_trace(go.Scatter(x=x_col, y=df["discharge_mw"], name="Battery Discharge", stackgroup='one', fillcolor="#32CD32", line=dict(width=0)))
            if "unmet_mw" in df.columns:
                fig_disp.add_trace(go.Scatter(x=x_col, y=df["unmet_mw"], name="Unmet Demand", stackgroup='one', fillcolor="#FF0000", line=dict(width=0)))
            fig_disp.update_layout(title=f"Dispatch (Area): {selected_for_dispatch}", barmode="stack", xaxis_title=x_title, yaxis_title="MWh")
            st.plotly_chart(fig_disp, use_container_width=True)
