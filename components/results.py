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
    disp_cols = ["hour", "demand_mw", "solar_mw", "wind_mw", "thermal_mw", "total_generation_mw"]
    rename_cols = {
        "hour": "Hour", "demand_mw": "Demand (MWh)",
        "solar_mw": "Solar (MWh)", "wind_mw": "Wind (MWh)",
        "thermal_mw": "Thermal (MWh)", "total_generation_mw": "Total Gen (MWh)"
    }
    
    for col, title in [
        ("charge_mw", "Charge (MWh)"), 
        ("discharge_mw", "Discharge (MWh)"), 
        ("soc_mwh", "SOC (MWh)"), 
        ("unmet_mw", "Unmet (MWh)"), 
        ("shadow_price", "Shadow Price (₹)")
    ]:
        if col in df.columns:
            disp_cols.append(col)
            rename_cols[col] = title

    display_df = df[disp_cols].copy().rename(columns=rename_cols).round(2)
    if "timestamp" in df.columns:
        display_df.insert(0, "Timestamp", df["timestamp"])
    
    # Large dataset handling for dataframe view
    if len(display_df) > 1000:
        st.caption(f"Showing first 1000 of {len(display_df)} rows for performance.")
        st.dataframe(display_df.head(1000), use_container_width=True, height=400)
    else:
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
    
    # Use timestamp for x-axis if available, otherwise hour
    x_col = df["timestamp"] if "timestamp" in df.columns else df["hour"]
    x_title = "Time" if "timestamp" in df.columns else "Hour"
    marker_mode = "lines" if len(df) > 100 else "lines+markers"

    # Chart A: Demand vs Total Generation
    fig_a = go.Figure()
    fig_a.add_trace(go.Scatter(x=x_col, y=df["demand_mw"], name="Demand", mode=marker_mode, line=dict(color="red", width=2, dash="dash")))
    fig_a.add_trace(go.Scatter(x=x_col, y=df["total_generation_mw"], name="Total Generation", mode=marker_mode, line=dict(color="blue", width=2)))
    fig_a.update_layout(title="Chart A: Demand vs Total Generation", xaxis_title=x_title, yaxis_title="MWh")
    st.plotly_chart(fig_a, use_container_width=True)

    # Chart B: Hourly Dispatch by Source
    fig_b = go.Figure()
    fig_b.add_trace(go.Scatter(x=x_col, y=df["solar_mw"], name="Solar", stackgroup='one', fillcolor="#FFA500", line=dict(width=0)))
    fig_b.add_trace(go.Scatter(x=x_col, y=df["wind_mw"], name="Wind", stackgroup='one', fillcolor="#1E90FF", line=dict(width=0)))
    fig_b.add_trace(go.Scatter(x=x_col, y=df["thermal_mw"], name="Thermal", stackgroup='one', fillcolor="#808080", line=dict(width=0)))
    if "discharge_mw" in df.columns:
        fig_b.add_trace(go.Scatter(x=x_col, y=df["discharge_mw"], name="Battery Discharge", stackgroup='one', fillcolor="#32CD32", line=dict(width=0)))
    if "unmet_mw" in df.columns:
        fig_b.add_trace(go.Scatter(x=x_col, y=df["unmet_mw"], name="Unmet Demand", stackgroup='one', fillcolor="#FF0000", line=dict(width=0)))
    fig_b.update_layout(title="Chart B: Dispatch Stack (Area)", xaxis_title=x_title, yaxis_title="MWh")
    st.plotly_chart(fig_b, use_container_width=True)

    # Phase 2 Charts
    if "soc_mwh" in df.columns:
        fig_batt = go.Figure()
        fig_batt.add_trace(go.Scatter(x=x_col, y=df["soc_mwh"], name="State of Charge", fill='tozeroy', marker_color="#9370DB"))
        fig_batt.update_layout(title="Phase 2: Battery State of Charge (SOC)", xaxis_title=x_title, yaxis_title="MWh")
        st.plotly_chart(fig_batt, use_container_width=True)

    if "shadow_price" in df.columns:
        fig_sp = go.Figure()
        fig_sp.add_trace(go.Scatter(x=x_col, y=df["shadow_price"], name="Shadow Price", mode=marker_mode, line=dict(color="#FF1493", width=1)))
        fig_sp.update_layout(title="Phase 2: Shadow Prices (Marginal Cost of Energy)", xaxis_title=x_title, yaxis_title="₹/MWh")
        st.plotly_chart(fig_sp, use_container_width=True)

    # Chart C & D: Pies
    energy_mix = {"Solar": df["solar_mw"].sum(), "Wind": df["wind_mw"].sum(), "Thermal": df["thermal_mw"].sum()}
    if "discharge_mw" in df.columns:
        energy_mix["Battery Discharge"] = df["discharge_mw"].sum()
    
    fig_c = px.pie(names=list(energy_mix.keys()), values=list(energy_mix.values()), title="Chart C: Energy Mix")
    
    cost_data = {"Solar": metrics["solar_cost"], "Wind": metrics["wind_cost"], "Thermal": metrics["thermal_cost"]}
    fig_d = px.pie(names=list(cost_data.keys()), values=list(cost_data.values()), title="Chart D: Cost Breakdown")
    
    col_c, col_d = st.columns(2)
    col_c.plotly_chart(fig_c, use_container_width=True)
    col_d.plotly_chart(fig_d, use_container_width=True)

    # Monthly Aggregation
    if "timestamp" in df.columns and len(df) > 1000:
        st.subheader("📅 Monthly Analysis Summary")
        df_month = df.copy()
        df_month["month"] = df_month["timestamp"].dt.to_period("M")
        
        agg_cols = {
            "demand_mw": "sum", "solar_mw": "sum", "wind_mw": "sum", 
            "thermal_mw": "sum", "hour_total_cost": "sum", "thermal_co2_kg": "sum"
        }
        if "discharge_mw" in df.columns:
            agg_cols["discharge_mw"] = "sum"
            agg_cols["charge_mw"] = "sum"
        if "unmet_mw" in df.columns:
            agg_cols["unmet_mw"] = "sum"
            
        monthly = df_month.groupby("month").agg(agg_cols).reset_index()
        monthly["month"] = monthly["month"].astype(str)
        
        monthly["renewable_share_pct"] = (monthly["solar_mw"] + monthly["wind_mw"]) / monthly["demand_mw"] * 100
        
        # Display monthly table
        st.dataframe(monthly.round(2), use_container_width=True)
        
        # Monthly bar chart
        fig_m = px.bar(monthly, x="month", y=["solar_mw", "wind_mw", "thermal_mw"], title="Monthly Generation Mix", labels={"value": "MWh", "month": "Month"})
        st.plotly_chart(fig_m, use_container_width=True)
