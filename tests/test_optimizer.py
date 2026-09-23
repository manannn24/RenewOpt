import pytest
import pandas as pd
from src.optimizer import solve_dispatch, OptimizationResult

@pytest.fixture
def simple_data():
    """Minimal 2-hour dataset for quick LP verification."""
    demand_df = pd.DataFrame({"hour": [0, 1], "demand_mw": [400.0, 500.0]})
    solar_df = pd.DataFrame({"hour": [0, 1], "solar_available_mw": [100.0, 200.0]})
    wind_df = pd.DataFrame({"hour": [0, 1], "wind_available_mw": [150.0, 150.0]})
    generators_df = pd.DataFrame({
        "source": ["Solar", "Wind", "Thermal"],
        "max_capacity_mw": [400.0, 300.0, 800.0],
        "cost_per_mwh": [10.0, 15.0, 85.0],
        "co2_per_mwh": [0.0, 0.0, 820.0],
    })
    return demand_df, solar_df, wind_df, generators_df

@pytest.fixture
def default_data():
    """Load the project's default 24-hour dataset."""
    from src.data_loader import load_default_data
    b = load_default_data()
    return b.demand_df, b.solar_df, b.wind_df, b.generators_df


def test_1_known_small_lp_optimal(simple_data):
    """Test 1: Known small LP produces an optimal result."""
    demand_df, solar_df, wind_df, generators_df = simple_data
    result = solve_dispatch(demand_df, solar_df, wind_df, generators_df)
    assert result.status == "Optimal", f"Expected Optimal, got {result.status}"
    assert result.total_cost is not None
    assert result.total_cost > 0


def test_1_cost_minimized_solar_first(simple_data):
    """
    For the simple 2-hour case:
    - Solar costs 10/MWh, Wind 15/MWh, Thermal 85/MWh
    - Optimal solution should maximize cheap solar/wind, then fill with thermal.
    Hour 0: demand=400, solar_avail=100, wind_avail=150 -> solar=100, wind=150, thermal=150
    Hour 1: demand=500, solar_avail=200, wind_avail=150 -> solar=200, wind=150, thermal=150
    Expected total cost = (10*100 + 15*150 + 85*150) + (10*200 + 15*150 + 85*150)
                        = (1000 + 2250 + 12750) + (2000 + 2250 + 12750)
                        = 16000 + 17000 = 33000
    """
    demand_df, solar_df, wind_df, generators_df = simple_data
    result = solve_dispatch(demand_df, solar_df, wind_df, generators_df)
    assert result.status == "Optimal"
    expected_cost = 33000.0
    assert abs(result.total_cost - expected_cost) < 1.0, (
        f"Expected cost ~{expected_cost}, got {result.total_cost:.2f}"
    )


def test_2_zero_solar_dispatch(simple_data):
    """Test 2: Zero solar availability -> solar dispatch must be zero."""
    demand_df, solar_df, wind_df, generators_df = simple_data
    solar_df_zero = solar_df.copy()
    solar_df_zero["solar_available_mw"] = 0.0
    result = solve_dispatch(demand_df, solar_df_zero, wind_df, generators_df)
    assert result.status == "Optimal"
    assert result.dispatch_df["solar_mw"].sum() < 1e-6, "Solar dispatch must be zero when availability is zero"


def test_3_zero_wind_dispatch(simple_data):
    """Test 3: Zero wind availability -> wind dispatch must be zero."""
    demand_df, solar_df, wind_df, generators_df = simple_data
    wind_df_zero = wind_df.copy()
    wind_df_zero["wind_available_mw"] = 0.0
    result = solve_dispatch(demand_df, solar_df, wind_df_zero, generators_df)
    assert result.status == "Optimal"
    assert result.dispatch_df["wind_mw"].sum() < 1e-6, "Wind dispatch must be zero when availability is zero"


def test_4_demand_balance_every_hour(default_data):
    """Test 4: Every hour satisfies demand balance (total_gen == demand)."""
    demand_df, solar_df, wind_df, generators_df = default_data
    result = solve_dispatch(demand_df, solar_df, wind_df, generators_df)
    assert result.status == "Optimal"
    df = result.dispatch_df
    for _, row in df.iterrows():
        gen = row["solar_mw"] + row["wind_mw"] + row["thermal_mw"]
        diff = abs(gen - row["demand_mw"])
        assert diff < 1e-3, f"Hour {row['hour']}: demand balance violated (diff={diff:.6f})"


def test_5_no_dispatch_exceeds_availability(default_data):
    """Test 5: No dispatch value exceeds availability or capacity."""
    demand_df, solar_df, wind_df, generators_df = default_data
    result = solve_dispatch(demand_df, solar_df, wind_df, generators_df)
    assert result.status == "Optimal"
    df = result.dispatch_df
    solar_avail = solar_df.set_index("hour")["solar_available_mw"]
    wind_avail = wind_df.set_index("hour")["wind_available_mw"]
    thermal_cap = float(generators_df[generators_df["source"]=="Thermal"]["max_capacity_mw"].values[0])
    TOL = 1e-4
    for _, row in df.iterrows():
        h = int(row["hour"])
        assert row["solar_mw"] <= solar_avail[h] + TOL, f"Hour {h}: solar exceeds availability"
        assert row["wind_mw"] <= wind_avail[h] + TOL, f"Hour {h}: wind exceeds availability"
        assert row["thermal_mw"] <= thermal_cap + TOL, f"Hour {h}: thermal exceeds capacity"
        assert row["solar_mw"] >= -TOL, f"Hour {h}: negative solar"
        assert row["wind_mw"] >= -TOL, f"Hour {h}: negative wind"
        assert row["thermal_mw"] >= -TOL, f"Hour {h}: negative thermal"


def test_8_infeasible_dataset_returns_infeasible():
    """Test 8: Infeasible dataset returns infeasible status (not a crash)."""
    demand_df = pd.DataFrame({"hour": [0], "demand_mw": [10000.0]})  # Way too high
    solar_df = pd.DataFrame({"hour": [0], "solar_available_mw": [100.0]})
    wind_df = pd.DataFrame({"hour": [0], "wind_available_mw": [100.0]})
    generators_df = pd.DataFrame({
        "source": ["Solar", "Wind", "Thermal"],
        "max_capacity_mw": [100.0, 100.0, 100.0],
        "cost_per_mwh": [10.0, 15.0, 85.0],
        "co2_per_mwh": [0.0, 0.0, 820.0],
    })
    result = solve_dispatch(demand_df, solar_df, wind_df, generators_df)
    assert result.status == "Infeasible", f"Expected Infeasible, got {result.status}"
    assert result.dispatch_df is None
    assert result.total_cost is None


def test_9_total_cost_equals_source_costs(default_data):
    """Test 9: Total cost equals sum of source-level costs."""
    demand_df, solar_df, wind_df, generators_df = default_data
    result = solve_dispatch(demand_df, solar_df, wind_df, generators_df)
    assert result.status == "Optimal"
    df = result.dispatch_df
    sum_source_costs = df["solar_cost"].sum() + df["wind_cost"].sum() + df["thermal_cost"].sum()
    assert abs(sum_source_costs - result.total_cost) < 1.0, (
        f"Source cost sum ({sum_source_costs:.2f}) != total_cost ({result.total_cost:.2f})"
    )
