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
        st.markdown(r"""
**Decision Variables** (for each hour $t = 0, 1, ..., 23$):
- $S_t$ = Solar generation (MWh)
- $W_t$ = Wind generation (MWh)  
- $T_t$ = Thermal generation (MWh)

**Objective Function (Minimize)**:
$$Z = \sum_{t=0}^{23} \left( C_s \cdot S_t + C_w \cdot W_t + C_{th} \cdot T_t \right)$$

where $C_s, C_w, C_{th}$ are the cost per MWh for solar, wind, and thermal.

**Constraints**:

| Constraint | Equation | Type |
|-----------|----------|------|
| Demand Balance | $S_t + W_t + T_t = D_t$ | Equality |
| Solar Availability | $S_t \leq \text{SolarAvail}_t$ | Upper bound |
| Wind Availability | $W_t \leq \text{WindAvail}_t$ | Upper bound |
| Thermal Capacity | $T_t \leq \text{ThermalCap}$ | Upper bound |
| Non-Negativity | $S_t, W_t, T_t \geq 0$ | Lower bound |

**Number of decision variables:** 72 (24 × 3 sources)  
**Number of constraints:** 24 hourly demand-balance equality constraints, with variable bounds enforcing non-negativity, renewable availability, and thermal capacity.
        """)

    bundle = st.session_state.bundle

    # Validation check
    validation = validate_data(
        bundle.demand_df, bundle.solar_df, bundle.wind_df, bundle.generators_df
    )
    if not validation.is_valid:
        st.error("❌ Dataset Validation Failed. Please fix the following errors in Input Configuration:")
        for err in validation.errors:
            st.error(f"- {err}")
        st.stop()

    # Feasibility check
    st.subheader("Pre-Optimization Feasibility Check")
    infeasible_hours = check_feasibility(
        bundle.demand_df, bundle.solar_df, bundle.wind_df, bundle.generators_df
    )
    if infeasible_hours:
        st.warning(f"⚠️ {len(infeasible_hours)} hour(s) may be infeasible before optimization:")
        for h in infeasible_hours:
            st.warning(
                f"Hour {h['hour']}: Demand={h['demand']:.0f} MW, "
                f"Max Available={h['max_available']:.0f} MW, "
                f"Shortfall={h['shortfall']:.0f} MW"
            )
    else:
        st.success("✅ All 24 hours are pre-feasibility checked: supply can meet demand.")

    st.divider()
    if st.button("▶️ Run LP Optimization", type="primary", use_container_width=True):
        with st.spinner("Solving LP with CBC solver..."):

            result = solve_dispatch(
                bundle.demand_df, bundle.solar_df, bundle.wind_df, bundle.generators_df
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
        bundle.demand_df, bundle.solar_df, bundle.wind_df, bundle.generators_df
    )
