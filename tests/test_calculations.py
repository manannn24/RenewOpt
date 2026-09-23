import pytest
import pandas as pd
from src.calculations import (
    calculate_total_cost,
    calculate_renewable_generation,
    calculate_renewable_share,
    calculate_thermal_dependency,
    calculate_total_emissions,
    build_metrics,
)
from src.optimizer import solve_dispatch

@pytest.fixture
def sample_dispatch_df():
    """A known 2-hour dispatch result."""
    return pd.DataFrame({
        "hour": [0, 1],
        "demand_mw": [400.0, 500.0],
        "solar_mw": [100.0, 200.0],
        "wind_mw": [150.0, 150.0],
        "thermal_mw": [150.0, 150.0],
        "total_generation_mw": [400.0, 500.0],
        "solar_cost": [1000.0, 2000.0],
        "wind_cost": [2250.0, 2250.0],
        "thermal_cost": [12750.0, 12750.0],
        "hour_total_cost": [16000.0, 17000.0],
    })

@pytest.fixture
def generators_df():
    return pd.DataFrame({
        "source": ["Solar", "Wind", "Thermal"],
        "max_capacity_mw": [400.0, 300.0, 800.0],
        "cost_per_mwh": [10.0, 15.0, 85.0],
        "co2_per_mwh": [0.0, 0.0, 820.0],
    })


def test_total_cost(sample_dispatch_df):
    """Total cost = sum of hour_total_cost."""
    cost = calculate_total_cost(sample_dispatch_df)
    assert abs(cost - 33000.0) < 1e-6


def test_renewable_generation(sample_dispatch_df):
    """Renewable generation = solar + wind total."""
    renewable = calculate_renewable_generation(sample_dispatch_df)
    # solar: 100+200=300, wind: 150+150=300, total=600
    assert abs(renewable - 600.0) < 1e-6


def test_10_renewable_share_correct(sample_dispatch_df):
    """Test 10: Renewable share is mathematically correct."""
    share = calculate_renewable_share(sample_dispatch_df)
    # total_gen = 400+500=900, renewable = 600, share = 600/900*100 = 66.667%
    expected = 600.0 / 900.0 * 100.0
    assert abs(share - expected) < 1e-4


def test_thermal_dependency(sample_dispatch_df):
    """Thermal dependency = thermal / total * 100."""
    dep = calculate_thermal_dependency(sample_dispatch_df)
    # thermal = 300, total = 900
    expected = 300.0 / 900.0 * 100.0
    assert abs(dep - expected) < 1e-4


def test_emissions_thermal_only(sample_dispatch_df, generators_df):
    """Emissions: only thermal emits CO2."""
    emissions = calculate_total_emissions(sample_dispatch_df, generators_df)
    # thermal = 300 MWh * 820 kg/MWh = 246000 kg
    assert abs(emissions["solar_kg_co2"] - 0.0) < 1e-6
    assert abs(emissions["wind_kg_co2"] - 0.0) < 1e-6
    assert abs(emissions["thermal_kg_co2"] - 300.0 * 820.0) < 1e-6
    assert abs(emissions["total_kg_co2"] - 300.0 * 820.0) < 1e-6


def test_build_metrics_complete(sample_dispatch_df, generators_df):
    """build_metrics returns all required keys."""
    metrics = build_metrics(sample_dispatch_df, generators_df)
    required_keys = [
        "total_demand_mwh", "total_generation_mwh", "renewable_generation_mwh",
        "renewable_share_pct", "thermal_dependency_pct",
        "total_cost", "solar_cost", "wind_cost", "thermal_cost",
        "solar_kg_co2", "wind_kg_co2", "thermal_kg_co2", "total_kg_co2",
    ]
    for key in required_keys:
        assert key in metrics, f"Missing key: {key}"


def test_9_cost_sum_matches_optimizer():
    """Test 9: Source cost sum matches optimizer total_cost for default dataset."""
    from src.data_loader import load_default_data
    b = load_default_data()
    result = solve_dispatch(b.demand_df, b.solar_df, b.wind_df, b.generators_df)
    assert result.status == "Optimal"
    df = result.dispatch_df
    source_sum = df["solar_cost"].sum() + df["wind_cost"].sum() + df["thermal_cost"].sum()
    assert abs(source_sum - result.total_cost) < 1.0
