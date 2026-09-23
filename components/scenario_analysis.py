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
)

def render_scenario_analysis(demand_df, solar_df, wind_df, generators_df):
    """Render the Scenario Analysis page."""
    st.header("🔄 Scenario Analysis")
    st.markdown(
        "Compare different operating conditions by re-running the LP optimizer with modified inputs.\n\n"
        "**Note on Increased Renewable Capacity:** This scenario assumes that the newly added solar capacity "
        "has the same normalized hourly generation profile as the existing capacity (scaled proportionally)."
    )

    scenario_map = {
        "Baseline (Normal Conditions)": "Baseline",
        "High Demand (+20%)": "High Demand",
        "Low Solar (-50%)": "Low Solar",
        "High Thermal Cost (+30%)": "High Thermal Cost",
        "Increased Renewable Capacity (+200 MW Solar)": "Increased Renewable Capacity",
    }

    selected_scenarios = st.multiselect(
        "Select scenarios to run:",
        list(scenario_map.keys()),
        default=list(scenario_map.keys())[:3],
    )

    # Custom parameter sliders
    with st.expander("⚙️ Customize Scenario Parameters"):
        demand_mult = st.slider("High Demand multiplier", 1.0, 2.0, 1.20, 0.05)
        solar_mult = st.slider("Low Solar availability multiplier", 0.1, 1.0, 0.50, 0.05)
        thermal_cost_mult = st.slider("High Thermal Cost multiplier", 1.0, 3.0, 1.30, 0.05)
        solar_add_mw = st.slider("Solar Capacity Addition (MW)", 50.0, 500.0, 200.0, 50.0)

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
                    results[label] = run_high_demand(demand_df, solar_df, wind_df, generators_df, demand_mult)
                elif key == "Low Solar":
                    results[label] = run_low_solar(demand_df, solar_df, wind_df, generators_df, solar_mult)
                elif key == "High Thermal Cost":
                    results[label] = run_high_thermal_cost(demand_df, solar_df, wind_df, generators_df, thermal_cost_mult)
                elif key == "Increased Renewable Capacity":
                    results[label] = run_increased_renewable_capacity(
                        demand_df, solar_df, wind_df, generators_df, solar_add_mw
                    )
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
                    "Thermal Dependency (%)": f"{m['thermal_dependency_pct']:.1f}",
                    "CO₂ Emissions (kg)": f"{m['total_kg_co2']:,.0f}",
                })
            else:
                rows.append({
                    "Scenario": label,
                    "Status": f"❌ {sr.status}",
                    "Total Cost (₹)": "N/A",
                    "Renewable Share (%)": "N/A",
                    "Thermal Dependency (%)": "N/A",
                    "CO₂ Emissions (kg)": "N/A",
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # --- Comparative bar charts (only optimal scenarios) ---
        optimal_results = {k: v for k, v in results.items() if v.status == "Optimal" and v.metrics}
        if len(optimal_results) >= 2:
            st.subheader("📊 Comparative Charts")

            cost_data = {k: v.metrics["total_cost"] for k, v in optimal_results.items()}
            fig_cost = px.bar(
                x=list(cost_data.keys()), y=list(cost_data.values()),
                title="Total Generation Cost by Scenario",
                labels={"x": "Scenario", "y": "Cost (₹)"},
                color=list(cost_data.keys()),
            )
            st.plotly_chart(fig_cost, use_container_width=True)

            share_data = {k: v.metrics["renewable_share_pct"] for k, v in optimal_results.items()}
            fig_share = px.bar(
                x=list(share_data.keys()), y=list(share_data.values()),
                title="Renewable Share by Scenario",
                labels={"x": "Scenario", "y": "Renewable Share (%)"},
                color=list(share_data.keys()),
            )
            st.plotly_chart(fig_share, use_container_width=True)

            co2_data = {k: v.metrics["total_kg_co2"] for k, v in optimal_results.items()}
            fig_co2 = px.bar(
                x=list(co2_data.keys()), y=list(co2_data.values()),
                title="CO₂ Emissions by Scenario",
                labels={"x": "Scenario", "y": "CO₂ (kg)"},
                color=list(co2_data.keys()),
            )
            st.plotly_chart(fig_co2, use_container_width=True)

        # Show dispatch comparison for feasible scenarios
        if optimal_results:
            st.subheader("🗓️ Hourly Dispatch Comparison")
            selected_for_dispatch = st.selectbox(
                "View dispatch for scenario:",
                list(optimal_results.keys()),
            )
            sr = optimal_results[selected_for_dispatch]
            df = sr.result.dispatch_df
            fig_disp = go.Figure()
            fig_disp.add_trace(go.Bar(x=df["hour"], y=df["solar_mw"], name="Solar", marker_color="#FFA500"))
            fig_disp.add_trace(go.Bar(x=df["hour"], y=df["wind_mw"], name="Wind", marker_color="#1E90FF"))
            fig_disp.add_trace(go.Bar(x=df["hour"], y=df["thermal_mw"], name="Thermal", marker_color="#808080"))
            fig_disp.update_layout(
                title=f"Hourly Dispatch: {selected_for_dispatch}",
                barmode="stack",
                xaxis_title="Hour", yaxis_title="MWh",
            )
            st.plotly_chart(fig_disp, use_container_width=True)
