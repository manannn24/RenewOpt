import streamlit as st
from src.calculations import build_metrics

def render_dashboard(result, generators_df):
    """Render the main dashboard KPI cards and summary."""
    st.header("📊 Dashboard")
    st.markdown(
        """
        **RenewOpt** uses Linear Programming to determine the optimal hourly electricity 
        generation mix from Solar, Wind, and Thermal sources to minimize total generation cost 
        while satisfying 24-hour demand and respecting capacity/availability constraints.
        """
    )

    if result is None:
        st.info("No optimization result yet. Go to the **Optimization** page to run the LP solver.")
        return

    # Status indicator
    if result.status == "Optimal":
        st.success(f"✅ Status: {result.status} — {result.message}")
    elif result.status == "Infeasible":
        st.error(f"❌ Status: {result.status} — {result.message}")
        return
    else:
        st.warning(f"⚠️ Status: {result.status} — {result.message}")
        return

    if result.dispatch_df is None:
        return

    metrics = build_metrics(result.dispatch_df, generators_df)

    # KPI cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Total Demand",
            f"{metrics['total_demand_mwh']:,.0f} MWh",
            help="Sum of hourly electricity demand over 24 hours"
        )
    with col2:
        st.metric(
            "Min Generation Cost",
            f"₹{metrics['total_cost']:,.0f}",
            help="Minimum total generation cost from the LP optimizer"
        )
    with col3:
        st.metric(
            "Renewable Share",
            f"{metrics['renewable_share_pct']:.1f}%",
            help="Percentage of total generation from solar + wind"
        )
    with col4:
        st.metric(
            "CO₂ Emissions",
            f"{metrics['total_kg_co2']:,.0f} kg",
            help="Total estimated CO₂ emissions from the optimal dispatch"
        )

    # Secondary metrics row
    col5, col6, col7 = st.columns(3)
    with col5:
        st.metric("Thermal Dependency", f"{metrics['thermal_dependency_pct']:.1f}%")
    with col6:
        st.metric("Renewable Generation", f"{metrics['renewable_generation_mwh']:,.0f} MWh")
    with col7:
        st.metric("Total Generation", f"{metrics['total_generation_mwh']:,.0f} MWh")

    # Phase 2 metrics row (only show if present)
    has_p2_metrics = any(k in metrics for k in ["total_unmet_mwh", "peak_soc_mwh", "max_shadow_price"])
    if has_p2_metrics:
        st.subheader("Advanced Metrics (Phase 2)")
        col8, col9, col10, col11 = st.columns(4)
        
        unmet = metrics.get("total_unmet_mwh", 0.0)
        col8.metric("Unmet Demand", f"{unmet:,.1f} MWh", 
                   delta="⚠️ Penalty active" if unmet > 0 else None, delta_color="inverse")
        
        if "peak_soc_mwh" in metrics:
            col9.metric("Peak Battery SOC", f"{metrics['peak_soc_mwh']:,.1f} MWh")
            col10.metric("Total Discharge", f"{metrics.get('total_discharge_mwh', 0.0):,.1f} MWh")
        else:
            col9.metric("Battery Storage", "Disabled")
            col10.metric("Total Discharge", "N/A")
            
        if "max_shadow_price" in metrics:
            col11.metric("Max Shadow Price", f"₹{metrics['max_shadow_price']:,.2f}/MWh")
        else:
            col11.metric("Max Shadow Price", "N/A")
