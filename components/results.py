import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.calculations import build_metrics

def render_results(result, generators_df):
    """Render optimization results page with dispatch table and charts."""
    st.header("📈 Optimization Results")

    if result is None:
        st.info("No optimization result yet. Run the LP solver first.")
        return

    if result.status != "Optimal":
        st.error(f"Cannot display results: {result.message}")
        return

    df = result.dispatch_df
    metrics = build_metrics(df, generators_df)

    # --- Dispatch Table ---
    st.subheader("🗓️ Optimal Dispatch Table")
    display_df = df[["hour", "demand_mw", "solar_mw", "wind_mw", "thermal_mw", "total_generation_mw"]].copy()
    display_df = display_df.rename(columns={
        "hour": "Hour",
        "demand_mw": "Demand (MWh)",
        "solar_mw": "Solar (MWh)",
        "wind_mw": "Wind (MWh)",
        "thermal_mw": "Thermal (MWh)",
        "total_generation_mw": "Total Gen (MWh)",
    })
    display_df = display_df.round(2)
    st.dataframe(display_df, use_container_width=True, height=400)

    # --- Summary metrics ---
    st.subheader("📊 Summary Metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Cost", f"₹{metrics['total_cost']:,.0f}")
    col2.metric("Renewable Share", f"{metrics['renewable_share_pct']:.1f}%")
    col3.metric("Thermal Dependency", f"{metrics['thermal_dependency_pct']:.1f}%")
    col4.metric("Total CO₂", f"{metrics['total_kg_co2']:,.0f} kg")

    # --- Charts ---
    st.subheader("📉 Charts")

    # Chart A: Demand vs Total Generation
    fig_a = go.Figure()
    fig_a.add_trace(go.Scatter(
        x=df["hour"], y=df["demand_mw"],
        name="Demand", mode="lines+markers",
        line=dict(color="red", width=2, dash="dash"),
    ))
    fig_a.add_trace(go.Scatter(
        x=df["hour"], y=df["total_generation_mw"],
        name="Total Generation", mode="lines+markers",
        line=dict(color="blue", width=2),
    ))
    fig_a.update_layout(
        title="Chart A: Demand vs Total Generation",
        xaxis_title="Hour", yaxis_title="MWh",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
    )
    st.plotly_chart(fig_a, use_container_width=True)

    # Chart B: Hourly Dispatch by Source (stacked area)
    fig_b = go.Figure()
    fig_b.add_trace(go.Bar(x=df["hour"], y=df["solar_mw"], name="Solar", marker_color="#FFA500"))
    fig_b.add_trace(go.Bar(x=df["hour"], y=df["wind_mw"], name="Wind", marker_color="#1E90FF"))
    fig_b.add_trace(go.Bar(x=df["hour"], y=df["thermal_mw"], name="Thermal", marker_color="#808080"))
    fig_b.update_layout(
        title="Chart B: Hourly Dispatch by Source",
        barmode="stack",
        xaxis_title="Hour", yaxis_title="MWh",
    )
    st.plotly_chart(fig_b, use_container_width=True)

    # Chart C: Energy Mix (Pie)
    energy_mix = {
        "Solar": df["solar_mw"].sum(),
        "Wind": df["wind_mw"].sum(),
        "Thermal": df["thermal_mw"].sum(),
    }
    fig_c = px.pie(
        names=list(energy_mix.keys()),
        values=list(energy_mix.values()),
        title="Chart C: Overall Energy Mix",
        color_discrete_sequence=["#FFA500", "#1E90FF", "#808080"],
    )
    col_c, col_d = st.columns(2)
    col_c.plotly_chart(fig_c, use_container_width=True)

    # Chart D: Cost Breakdown (Pie)
    cost_data = {
        "Solar": metrics["solar_cost"],
        "Wind": metrics["wind_cost"],
        "Thermal": metrics["thermal_cost"],
    }
    fig_d = px.pie(
        names=list(cost_data.keys()),
        values=list(cost_data.values()),
        title="Chart D: Cost Breakdown by Source",
        color_discrete_sequence=["#FFA500", "#1E90FF", "#808080"],
    )
    col_d.plotly_chart(fig_d, use_container_width=True)

    # Chart E: Emissions Breakdown
    emission_data = {
        "Solar": metrics["solar_kg_co2"],
        "Wind": metrics["wind_kg_co2"],
        "Thermal": metrics["thermal_kg_co2"],
    }
    fig_e = px.bar(
        x=list(emission_data.keys()),
        y=list(emission_data.values()),
        title="Chart E: CO₂ Emissions by Source",
        labels={"x": "Source", "y": "CO₂ (kg)"},
        color=list(emission_data.keys()),
        color_discrete_sequence=["#FFA500", "#1E90FF", "#808080"],
    )
    st.plotly_chart(fig_e, use_container_width=True)
