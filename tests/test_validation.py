import pytest
import pandas as pd
from src.validation import validate_data, check_feasibility

@pytest.fixture
def valid_bundle():
    demand_df = pd.DataFrame({"hour": list(range(24)), "demand_mw": [600.0] * 24})
    solar_df = pd.DataFrame({"hour": list(range(24)), "solar_available_mw": [0.0] * 6 + [100.0] * 12 + [0.0] * 6})
    wind_df = pd.DataFrame({"hour": list(range(24)), "wind_available_mw": [150.0] * 24})
    generators_df = pd.DataFrame({
        "source": ["Solar", "Wind", "Thermal"],
        "max_capacity_mw": [400.0, 300.0, 800.0],
        "cost_per_mwh": [10.0, 15.0, 85.0],
        "co2_per_mwh": [0.0, 0.0, 820.0],
    })
    return demand_df, solar_df, wind_df, generators_df


def test_valid_data_passes(valid_bundle):
    """Valid data should pass validation."""
    demand_df, solar_df, wind_df, generators_df = valid_bundle
    result = validate_data(demand_df, solar_df, wind_df, generators_df)
    assert result.is_valid, f"Expected valid, errors: {result.errors}"


def test_6_negative_demand_rejected():
    """Test 6: Invalid negative demand is rejected."""
    demand_df = pd.DataFrame({"hour": [0, 1], "demand_mw": [-100.0, 500.0]})
    solar_df = pd.DataFrame({"hour": [0, 1], "solar_available_mw": [100.0, 200.0]})
    wind_df = pd.DataFrame({"hour": [0, 1], "wind_available_mw": [150.0, 150.0]})
    generators_df = pd.DataFrame({
        "source": ["Solar", "Wind", "Thermal"],
        "max_capacity_mw": [400.0, 300.0, 800.0],
        "cost_per_mwh": [10.0, 15.0, 85.0],
        "co2_per_mwh": [0.0, 0.0, 820.0],
    })
    result = validate_data(demand_df, solar_df, wind_df, generators_df)
    assert not result.is_valid
    assert any("negative" in e.lower() for e in result.errors)


def test_7_duplicate_hour_rejected():
    """Test 7: Duplicate hour is rejected."""
    demand_df = pd.DataFrame({"hour": [0, 0, 1], "demand_mw": [500.0, 500.0, 600.0]})
    solar_df = pd.DataFrame({"hour": [0, 1], "solar_available_mw": [100.0, 200.0]})
    wind_df = pd.DataFrame({"hour": [0, 1], "wind_available_mw": [150.0, 150.0]})
    generators_df = pd.DataFrame({
        "source": ["Solar", "Wind", "Thermal"],
        "max_capacity_mw": [400.0, 300.0, 800.0],
        "cost_per_mwh": [10.0, 15.0, 85.0],
        "co2_per_mwh": [0.0, 0.0, 820.0],
    })
    result = validate_data(demand_df, solar_df, wind_df, generators_df)
    assert not result.is_valid
    assert any("duplicate" in e.lower() for e in result.errors)


def test_missing_column_rejected():
    """Missing required column is rejected."""
    demand_df = pd.DataFrame({"hour": [0, 1]})  # Missing demand_mw
    solar_df = pd.DataFrame({"hour": [0, 1], "solar_available_mw": [100.0, 200.0]})
    wind_df = pd.DataFrame({"hour": [0, 1], "wind_available_mw": [150.0, 150.0]})
    generators_df = pd.DataFrame({
        "source": ["Solar", "Wind", "Thermal"],
        "max_capacity_mw": [400.0, 300.0, 800.0],
        "cost_per_mwh": [10.0, 15.0, 85.0],
        "co2_per_mwh": [0.0, 0.0, 820.0],
    })
    result = validate_data(demand_df, solar_df, wind_df, generators_df)
    assert not result.is_valid


def test_availability_exceeds_capacity_rejected():
    """Solar availability exceeding capacity is rejected."""
    demand_df = pd.DataFrame({"hour": list(range(24)), "demand_mw": [600.0] * 24})
    solar_df = pd.DataFrame({"hour": list(range(24)), "solar_available_mw": [500.0] * 24})  # > capacity
    wind_df = pd.DataFrame({"hour": list(range(24)), "wind_available_mw": [150.0] * 24})
    generators_df = pd.DataFrame({
        "source": ["Solar", "Wind", "Thermal"],
        "max_capacity_mw": [400.0, 300.0, 800.0],  # Solar cap = 400
        "cost_per_mwh": [10.0, 15.0, 85.0],
        "co2_per_mwh": [0.0, 0.0, 820.0],
    })
    result = validate_data(demand_df, solar_df, wind_df, generators_df)
    assert not result.is_valid
    assert any("Solar" in e for e in result.errors)


def test_missing_thermal_source_rejected():
    """Missing Thermal source in generators is rejected."""
    demand_df = pd.DataFrame({"hour": [0], "demand_mw": [400.0]})
    solar_df = pd.DataFrame({"hour": [0], "solar_available_mw": [100.0]})
    wind_df = pd.DataFrame({"hour": [0], "wind_available_mw": [100.0]})
    generators_df = pd.DataFrame({
        "source": ["Solar", "Wind"],
        "max_capacity_mw": [400.0, 300.0],
        "cost_per_mwh": [10.0, 15.0],
        "co2_per_mwh": [0.0, 0.0],
    })
    result = validate_data(demand_df, solar_df, wind_df, generators_df)
    assert not result.is_valid
    assert any("Thermal" in e for e in result.errors)


def test_non_numeric_demand_rejected():
    """Malformed non-numeric value in demand is rejected cleanly."""
    demand_df = pd.DataFrame({"hour": [0, 1], "demand_mw": [500.0, "abc"]})
    solar_df = pd.DataFrame({"hour": [0, 1], "solar_available_mw": [100.0, 200.0]})
    wind_df = pd.DataFrame({"hour": [0, 1], "wind_available_mw": [150.0, 150.0]})
    generators_df = pd.DataFrame({
        "source": ["Solar", "Wind", "Thermal"],
        "max_capacity_mw": [400.0, 300.0, 800.0],
        "cost_per_mwh": [10.0, 15.0, 85.0],
        "co2_per_mwh": [0.0, 0.0, 820.0],
    })
    result = validate_data(demand_df, solar_df, wind_df, generators_df)
    assert not result.is_valid
    assert any("non-numeric" in e.lower() for e in result.errors)


def test_non_numeric_generator_cost_rejected():
    """Malformed non-numeric value in generator cost is rejected cleanly."""
    demand_df = pd.DataFrame({"hour": [0], "demand_mw": [500.0]})
    solar_df = pd.DataFrame({"hour": [0], "solar_available_mw": [100.0]})
    wind_df = pd.DataFrame({"hour": [0], "wind_available_mw": [150.0]})
    generators_df = pd.DataFrame({
        "source": ["Solar", "Wind", "Thermal"],
        "max_capacity_mw": [400.0, 300.0, 800.0],
        "cost_per_mwh": [10.0, "free", 85.0],
        "co2_per_mwh": [0.0, 0.0, 820.0],
    })
    result = validate_data(demand_df, solar_df, wind_df, generators_df)
    assert not result.is_valid
    assert any("non-numeric" in e.lower() for e in result.errors)


def test_missing_hour_in_solar_rejected(valid_bundle):
    """Missing an hour (e.g., hour 12) in solar dataset is rejected."""
    demand_df, solar_df, wind_df, generators_df = valid_bundle
    # Drop hour 12
    solar_df = solar_df[solar_df["hour"] != 12]
    result = validate_data(demand_df, solar_df, wind_df, generators_df)
    assert not result.is_valid
    assert any("missing hours" in e.lower() for e in result.errors)
    assert any("solar_availability" in e for e in result.errors)


def test_missing_hour_in_wind_rejected(valid_bundle):
    """Missing an hour (e.g., hour 5) in wind dataset is rejected."""
    demand_df, solar_df, wind_df, generators_df = valid_bundle
    # Drop hour 5
    wind_df = wind_df[wind_df["hour"] != 5]
    result = validate_data(demand_df, solar_df, wind_df, generators_df)
    assert not result.is_valid
    assert any("missing hours" in e.lower() for e in result.errors)
    assert any("wind_availability" in e for e in result.errors)


def test_mismatched_hour_sets_rejected(valid_bundle):
    """Mismatched hour sets (demand missing 1, solar missing 2) are rejected."""
    demand_df, solar_df, wind_df, generators_df = valid_bundle
    demand_df = demand_df[demand_df["hour"] != 1]
    solar_df = solar_df[solar_df["hour"] != 2]
    result = validate_data(demand_df, solar_df, wind_df, generators_df)
    assert not result.is_valid
    
    error_texts = " ".join(result.errors).lower()
    assert "missing hours" in error_texts
    assert "demand" in error_texts
    assert "solar_availability" in error_texts
