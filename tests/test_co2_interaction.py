import pytest
import pandas as pd
import numpy as np
from src.data_loader import load_default_data, build_phase2_config
from src.optimizer import solve_dispatch, Phase2Config
from src.validation import validate_co2_cap

class TestCO2Interaction:
    @pytest.fixture
    def demo_data(self):
        bundle = load_default_data()
        return bundle

    def test_24_hour_co2_cap_loading(self, demo_data):
        """Test that the default 24-hour CO2 cap is loaded correctly."""
        assert demo_data.co2_cap_df is not None
        assert "hour" in demo_data.co2_cap_df.columns
        assert "co2_cap_kg" in demo_data.co2_cap_df.columns

    def test_exact_0_to_23_coverage(self, demo_data):
        """Test exact hour coverage and validation."""
        errors = validate_co2_cap(demo_data.co2_cap_df)
        assert len(errors) == 0
        assert list(demo_data.co2_cap_df["hour"]) == list(range(24))

        bad_df = demo_data.co2_cap_df.copy()
        bad_df = bad_df.drop(0)
        assert len(validate_co2_cap(bad_df)) > 0

    def test_non_binding_co2_cap(self, demo_data):
        """Test behavior when the CO2 cap is high and non-binding."""
        cfg = Phase2Config(enable_co2_cap=True, co2_cap_df=demo_data.co2_cap_df, enable_battery=False)
        # 1,000,000 kg is very high, let's make it 10,000,000 kg to be absolutely sure
        df = demo_data.co2_cap_df.copy()
        df["co2_cap_kg"] = 10000000
        cfg.co2_cap_df = df
        
        res_baseline = solve_dispatch(
            demo_data.demand_df, demo_data.solar_df, demo_data.wind_df, demo_data.generators_df
        )
        res_capped = solve_dispatch(
            demo_data.demand_df, demo_data.solar_df, demo_data.wind_df, demo_data.generators_df, cfg
        )
        
        assert res_capped.status == "Optimal"
        assert abs(res_baseline.total_cost - res_capped.total_cost) < 0.1

    def test_infeasible_co2_cap(self, demo_data):
        """Test strict model infeasibility when CO2 cap is impossibly low."""
        cfg = Phase2Config(enable_co2_cap=True, enable_battery=False)
        df = demo_data.co2_cap_df.copy()
        df["co2_cap_kg"] = 10  # almost zero thermal allowed
        cfg.co2_cap_df = df
        
        res = solve_dispatch(
            demo_data.demand_df, demo_data.solar_df, demo_data.wind_df, demo_data.generators_df, cfg
        )
        assert res.status == "Infeasible"

    def test_co2_and_battery_interaction_demo_case(self, demo_data):
        """Test the specific CO2 + battery interaction for the demo case."""
        # Using the actual demo config
        overrides = {
            "enable_ramp": False,
            "enable_co2_cap": True,
            "enable_battery": True,
            "enable_reliability": False,
        }
        cfg = build_phase2_config(demo_data, overrides)
        # Ensure we have our 550000 demo caps
        assert cfg.co2_cap_df.loc[18, "co2_cap_kg"] == 550000
        
        res = solve_dispatch(
            demo_data.demand_df, demo_data.solar_df, demo_data.wind_df, demo_data.generators_df, cfg
        )
        
        assert res.status == "Optimal", res.message
        df = res.dispatch_df
        
        # Unmet demand should be 0
        assert res.total_unmet_demand == 0.0
        
        # Check binding behavior at hour 18
        thermal_hr18 = df.loc[df["hour"] == 18, "thermal_mw"].values[0]
        co2_hr18 = thermal_hr18 * 820
        # Should be binding or very close
        assert abs(co2_hr18 - 550000) < 1.0
        
        # Check battery discharge at hour 18
        discharge_hr18 = df.loc[df["hour"] == 18, "discharge_mw"].values[0]
        assert discharge_hr18 > 0
        
        # Check battery charge before hour 17
        total_charge_before_17 = df.loc[df["hour"] < 17, "charge_mw"].sum()
        assert total_charge_before_17 > 0
