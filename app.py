import streamlit as st
from src.data_loader import load_default_data
from src.validation import validate_data, check_feasibility
from src.optimizer import solve_dispatch
from src.calculations import build_metrics
from components.dashboard import render_dashboard
from components.input_config import render_input_config
from components.results import render_results
from components.scenario_analysis import render_scenario_analysis

# ----- Page Configuration -----
st.set_page_config(
    page_title="RenewOpt: Energy Dispatch Optimization",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----- Session State Initialization -----
if "result" not in st.session_state:
    st.session_state.result = None
if "bundle" not in st.session_state:
    st.session_state.bundle = load_default_data()
if "validation" not in st.session_state:
    st.session_state.validation = None
if "scenario_results" not in st.session_state:
    st.session_state.scenario_results = None

# ----- Sidebar -----
with st.sidebar:
    st.title("⚡ RenewOpt")
    st.caption("Renewable Energy Grid Dispatch Optimization")
    st.divider()

    page = st.radio(
        "Navigate",
        [
            "📊 Dashboard",
            "⚙️ Input Configuration",
            "🔬 Optimization",
            "📈 Results",
            "🔄 Scenario Analysis",
        ],
    )
    st.divider()
    st.caption("Academic OR Mini-Project")
    st.caption("PuLP + CBC Solver")

# ----- Pages -----
if page == "📊 Dashboard":
    render_dashboard(st.session_state.result, st.session_state.bundle.generators_df)

elif page == "⚙️ Input Configuration":
    new_bundle = render_input_config()
    if new_bundle is not None:
        # Reset result if data changed
        if new_bundle is not st.session_state.bundle:
            st.session_state.result = None
            st.session_state.scenario_results = None
        st.session_state.bundle = new_bundle

elif page == "🔬 Optimization":
    st.header("🔬 LP Optimization")
    st.subheader("Mathematical Model Summary")

    with st.expander("📐 View Full Mathematical Formulation", expanded=True):
        st.markdown(rf"""
**Decision Variables** (for each hour $t = 0, 1, ..., N-1$):
- $S_t$ = Solar generation (MWh)
- $W_t$ = Wind generation (MWh)  
- $T_t$ = Thermal generation (MWh)
- **Phase 2 Variables:** $C_t$ (Charge), $D_t$ (Discharge), $SOC_t$ (State of Charge), $Unmet_t$ (Unmet Demand)

**Objective Function (Minimize)**:
$$Z = \sum_{{t=0}}^{{N-1}} \left( C_s \cdot S_t + C_w \cdot W_t + C_{{th}} \cdot T_t + P_{{unmet}} \cdot Unmet_t \right)$$

**Constraints**:

| Constraint | Equation | Type |
|-----------|----------|------|
| Demand Balance | $S_t + W_t + T_t + D_t - C_t + Unmet_t = Demand_t$ | Equality |
| Solar Availability | $S_t \leq \text{{SolarAvail}}_t$ | Upper bound |
| Wind Availability | $W_t \leq \text{{WindAvail}}_t$ | Upper bound |
| Thermal Capacity | $T_t \leq \text{{ThermalCap}}$ | Upper bound |
| Thermal Ramp | $\|T_t - T_{{t-1}}\| \leq \text{{RampLimit}}$ | Phase 2 |
| Hourly CO2 Cap | $T_t \cdot \text{{CO2}}_{{th}} \leq \text{{CO2Cap}}_t$ | Phase 2 |
| Battery Dynamics | $SOC_t = SOC_{{t-1}} + \eta_c C_t - D_t / \eta_d$ | Phase 2 |
| Non-Negativity | $S_t, W_t, T_t, C_t, D_t, Unmet_t \geq 0$ | Lower bound |
        """)

    bundle = st.session_state.bundle
    dataset_length = len(bundle.demand_df)
    
    st.info(f"📅 Active Model Horizon: {dataset_length} hours")

    # Validation check
    from src.validation import validate_co2_cap, validate_battery_config, validate_ramp_config
    validation = validate_data(
        bundle.demand_df, bundle.solar_df, bundle.wind_df, bundle.generators_df
    )
    if not validation.is_valid:
        st.error("❌ Dataset Validation Failed. Please fix the following errors in Input Configuration:")
        for err in validation.errors:
            st.error(f"- {err}")
        st.stop()

    # Phase 2 UI Config
    st.subheader("Advanced Configuration (Phase 2)")
    col_a, col_b, col_c = st.columns(3)
    enable_ramp = col_a.checkbox("Enable Thermal Ramp Constraints", value=False)
    enable_co2 = col_b.checkbox("Enable Hourly CO₂ Cap", value=False)
    enable_battery = col_c.checkbox("Enable Battery Storage", value=False)
    enable_reliability = col_a.checkbox("Enable Reliability Mode (Allow Unmet Demand)", value=False)
    initial_thermal = 400.0
    if enable_ramp:
        initial_thermal = col_b.number_input("Initial Thermal Output (MW)", min_value=0.0, value=400.0)

    overrides = {
        "enable_ramp": enable_ramp,
        "enable_co2_cap": enable_co2,
        "enable_battery": enable_battery,
        "enable_reliability": enable_reliability,
        "initial_thermal_output_mw": initial_thermal,
    }
    from src.data_loader import build_phase2_config
    phase2_cfg = build_phase2_config(bundle, overrides)

    # Validate Phase 2 Config
    p2_errors = []
    if enable_co2:
        p2_errors += validate_co2_cap(bundle.co2_cap_df)
    if enable_battery:
        p2_errors += validate_battery_config(phase2_cfg)
    if enable_ramp:
        p2_errors += validate_ramp_config(phase2_cfg, bundle.generators_df)
    
    if p2_errors:
        st.error("❌ Phase 2 Configuration Validation Failed:")
        for err in p2_errors:
            st.error(f"- {err}")
        st.stop()

    # Feasibility check
    st.subheader("Pre-Optimization Feasibility Check")
    infeasible_hours = check_feasibility(
        bundle.demand_df, bundle.solar_df, bundle.wind_df, bundle.generators_df
    )
    if infeasible_hours and not enable_reliability and not enable_battery:
        st.warning(f"⚠️ {len(infeasible_hours)} hour(s) may be infeasible before optimization:")
        for h in infeasible_hours[:10]: # cap display
            st.warning(
                f"Hour {h['hour']}: Demand={h['demand']:.0f} MW, "
                f"Max Available={h['max_available']:.0f} MW, "
                f"Shortfall={h['shortfall']:.0f} MW"
            )
        if len(infeasible_hours) > 10:
            st.warning(f"... and {len(infeasible_hours) - 10} more.")
    elif infeasible_hours:
        st.info(f"ℹ️ {len(infeasible_hours)} hour(s) have demand exceeding generation capacity, but Battery or Reliability mode might resolve it.")
    else:
        st.success(f"✅ All {dataset_length} hours are pre-feasibility checked: supply can meet demand.")

    st.divider()
    if st.button("▶️ Run LP Optimization", type="primary", use_container_width=True):
        with st.spinner("Solving LP with CBC solver..."):

            result = solve_dispatch(
                bundle.demand_df, bundle.solar_df, bundle.wind_df, bundle.generators_df, phase2_cfg
            )
            st.session_state.result = result

        if result.status == "Optimal":
            st.success(f"✅ Optimal Solution Found!")
            st.info(f"Solver Status: {result.solver_status}")
            st.info(f"Total Cost: ₹{result.total_cost:,.2f}")
            if result.is_verified:
                st.success("✅ Post-solve verification: All constraints satisfied.")
            else:
                st.warning("⚠️ Post-solve verification found issues. Check Results page.")
        elif result.status == "Infeasible":
            st.error(f"❌ LP Infeasible: {result.message}")
        else:
            st.warning(f"⚠️ Solver Status: {result.message}")

elif page == "📈 Results":
    render_results(st.session_state.result, st.session_state.bundle.generators_df)

elif page == "🔄 Scenario Analysis":
    bundle = st.session_state.bundle
    render_scenario_analysis(
        bundle.demand_df, bundle.solar_df, bundle.wind_df, bundle.generators_df, bundle.co2_cap_df
    )
