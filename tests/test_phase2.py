"""
Phase 2 Tests for RenewOpt.

Tests shadow prices, thermal ramp, CO2 cap, battery storage,
reliability mode, and integrated model behavior.
"""

import pytest
import pandas as pd
import numpy as np
from src.optimizer import solve_dispatch, Phase2Config, OptimizationResult
from src.validation import validate_co2_cap, validate_battery_config, validate_ramp_config
from src.data_loader import load_default_data


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def default_data():
    """Load the project's default 24-hour dataset."""
    b = load_default_data()
    return b.demand_df, b.solar_df, b.wind_df, b.generators_df


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
def default_co2_cap():
    """Default CO2 cap data for 24 hours."""
    b = load_default_data()
    return b.co2_cap_df


# ============================================================
# Shadow Price Tests
# ============================================================

class TestShadowPrices:
    def test_shadow_prices_exist_for_each_hour(self, default_data):
        """Shadow prices extracted for every demand-balance hour."""
        demand_df, solar_df, wind_df, generators_df = default_data
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df)
        assert result.status == "Optimal"
        assert result.shadow_prices is not None
        assert len(result.shadow_prices) == 24

    def test_shadow_prices_finite(self, default_data):
        """All shadow prices are finite numbers."""
        demand_df, solar_df, wind_df, generators_df = default_data
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df)
        for t, sp in result.shadow_prices.items():
            assert np.isfinite(sp), f"Hour {t}: shadow price not finite ({sp})"

    def test_shadow_price_in_dispatch_df(self, default_data):
        """Shadow price column is in the dispatch DataFrame."""
        demand_df, solar_df, wind_df, generators_df = default_data
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df)
        assert "shadow_price" in result.dispatch_df.columns
        assert len(result.dispatch_df["shadow_price"]) == 24

    def test_shadow_price_sign_convention(self, default_data):
        """
        In the default dataset, thermal is the marginal generator at most hours.
        The shadow price should reflect the marginal cost of meeting one more unit
        of demand. With PuLP/CBC and equality constraints, the dual (pi) for 
        demand balance represents the marginal cost. For hours where thermal is 
        marginal, the shadow price magnitude should be close to the thermal cost.
        
        Note: PuLP/CBC sign convention: for a >= constraint, pi >= 0; for == constraint,
        pi can be positive or negative. We check magnitude, not strict sign.
        """
        demand_df, solar_df, wind_df, generators_df = default_data
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df)
        # At night hours (0-5) when solar=0 and thermal fills the gap,
        # the shadow price magnitude should be near thermal cost (85).
        for t in [0, 1, 2, 3]:
            sp = abs(result.shadow_prices[t])
            assert 80 <= sp <= 90, f"Hour {t}: expected ~85, got {sp:.2f}"


# ============================================================
# Thermal Ramp Tests
# ============================================================

class TestThermalRamp:
    def test_ramp_feasible_default(self, default_data):
        """Default ramp limit (200 MW/hr) should be feasible."""
        demand_df, solar_df, wind_df, generators_df = default_data
        cfg = Phase2Config(enable_ramp=True, ramp_limit_mw_per_hour=200.0,
                          initial_thermal_output_mw=400.0)
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        assert result.is_verified

    def test_ramp_post_solve_verified(self, default_data):
        """Post-solve verification passes with ramp constraints."""
        demand_df, solar_df, wind_df, generators_df = default_data
        cfg = Phase2Config(enable_ramp=True, ramp_limit_mw_per_hour=200.0,
                          initial_thermal_output_mw=400.0)
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.is_verified, "Post-solve verification should pass"

    def test_ramp_constraints_respected(self, default_data):
        """Thermal output changes never exceed ramp limit."""
        demand_df, solar_df, wind_df, generators_df = default_data
        ramp_limit = 200.0
        cfg = Phase2Config(enable_ramp=True, ramp_limit_mw_per_hour=ramp_limit,
                          initial_thermal_output_mw=400.0)
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        df = result.dispatch_df.sort_values("hour")
        thermals = df["thermal_mw"].tolist()
        # Check first hour vs initial
        assert abs(thermals[0] - 400.0) <= ramp_limit + 0.01
        # Check consecutive hours
        for i in range(1, len(thermals)):
            ramp = abs(thermals[i] - thermals[i-1])
            assert ramp <= ramp_limit + 0.01, f"Hour {i}: ramp {ramp:.2f} > {ramp_limit}"

    def test_tight_ramp_infeasible(self):
        """Extremely tight ramp (1 MW/hr) with high demand swing should be infeasible."""
        demand_df = pd.DataFrame({"hour": [0, 1], "demand_mw": [200.0, 800.0]})
        solar_df = pd.DataFrame({"hour": [0, 1], "solar_available_mw": [0.0, 0.0]})
        wind_df = pd.DataFrame({"hour": [0, 1], "wind_available_mw": [0.0, 0.0]})
        generators_df = pd.DataFrame({
            "source": ["Solar", "Wind", "Thermal"],
            "max_capacity_mw": [0.0, 0.0, 800.0],
            "cost_per_mwh": [10.0, 15.0, 85.0],
            "co2_per_mwh": [0.0, 0.0, 820.0],
        })
        cfg = Phase2Config(enable_ramp=True, ramp_limit_mw_per_hour=1.0,
                          initial_thermal_output_mw=200.0)
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Infeasible"

    def test_first_hour_ramp_from_initial(self):
        """First hour ramp is relative to initial_thermal_output_mw."""
        demand_df = pd.DataFrame({"hour": [0, 1], "demand_mw": [500.0, 500.0]})
        solar_df = pd.DataFrame({"hour": [0, 1], "solar_available_mw": [0.0, 0.0]})
        wind_df = pd.DataFrame({"hour": [0, 1], "wind_available_mw": [0.0, 0.0]})
        generators_df = pd.DataFrame({
            "source": ["Solar", "Wind", "Thermal"],
            "max_capacity_mw": [0.0, 0.0, 800.0],
            "cost_per_mwh": [10.0, 15.0, 85.0],
            "co2_per_mwh": [0.0, 0.0, 820.0],
        })
        # Initial at 200, demand 500, ramp=100 -> can only reach 300, infeasible
        cfg = Phase2Config(enable_ramp=True, ramp_limit_mw_per_hour=100.0,
                          initial_thermal_output_mw=200.0)
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Infeasible"


# ============================================================
# CO2 Cap Tests
# ============================================================

class TestCO2Cap:
    def test_non_binding_cap(self, default_data):
        """Very high CO2 cap doesn't change the optimal cost from baseline."""
        demand_df, solar_df, wind_df, generators_df = default_data
        # Non-binding cap
        co2_cap_df = pd.DataFrame({
            "hour": list(range(24)),
            "co2_cap_kg": [999999] * 24,
        })
        cfg = Phase2Config(enable_co2_cap=True, co2_cap_df=co2_cap_df)
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        # Cost should be same as baseline (~1,073,825)
        baseline = solve_dispatch(demand_df, solar_df, wind_df, generators_df)
        assert abs(result.total_cost - baseline.total_cost) < 1.0

    def test_binding_cap_changes_dispatch(self, default_data):
        """Binding CO2 cap at certain hours forces thermal down."""
        demand_df, solar_df, wind_df, generators_df = default_data
        co2_cap_df = pd.DataFrame({
            "hour": list(range(24)),
            "co2_cap_kg": [999999] * 17 + [200000] * 4 + [999999] * 3,
        })
        cfg = Phase2Config(enable_co2_cap=True, co2_cap_df=co2_cap_df,
                          enable_reliability=True, unmet_demand_penalty=50000.0)
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        # Check CO2 cap is respected at binding hours
        df = result.dispatch_df
        for t in [17, 18, 19, 20]:
            actual_co2 = float(df[df["hour"] == t]["thermal_co2_kg"].values[0])
            assert actual_co2 <= 200000 + 1.0

    def test_infeasible_co2_cap_strict(self, default_data):
        """Extremely tight CO2 cap with no battery/unmet demand → infeasible."""
        demand_df, solar_df, wind_df, generators_df = default_data
        co2_cap_df = pd.DataFrame({
            "hour": list(range(24)),
            "co2_cap_kg": [1.0] * 24,  # Impossibly tight
        })
        cfg = Phase2Config(enable_co2_cap=True, co2_cap_df=co2_cap_df,
                          enable_reliability=False)
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Infeasible"

    def test_co2_post_solve_verification(self, default_data, default_co2_cap):
        """Post-solve verification checks CO2 constraints."""
        demand_df, solar_df, wind_df, generators_df = default_data
        cfg = Phase2Config(enable_co2_cap=True, co2_cap_df=default_co2_cap)
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        if result.status == "Optimal":
            assert result.is_verified


# ============================================================
# CO2 Cap Validation Tests
# ============================================================

class TestCO2CapValidation:
    def test_valid_co2_cap(self):
        """Valid 24-hour CO2 cap passes validation."""
        df = pd.DataFrame({"hour": list(range(24)), "co2_cap_kg": [500000] * 24})
        errors = validate_co2_cap(df)
        assert len(errors) == 0

    def test_missing_hour_co2_cap(self):
        """CO2 cap with missing hour is rejected."""
        df = pd.DataFrame({"hour": list(range(23)), "co2_cap_kg": [500000] * 23})
        errors = validate_co2_cap(df)
        assert any("missing hours" in e.lower() for e in errors)

    def test_negative_co2_cap(self):
        """Negative CO2 cap value is rejected."""
        df = pd.DataFrame({"hour": list(range(24)), "co2_cap_kg": [-1] + [500000] * 23})
        errors = validate_co2_cap(df)
        assert any("negative" in e.lower() for e in errors)

    def test_none_co2_cap(self):
        """None CO2 cap DataFrame is rejected."""
        errors = validate_co2_cap(None)
        assert len(errors) > 0


# ============================================================
# Battery Tests
# ============================================================

class TestBattery:
    def test_battery_soc_bounds_respected(self, default_data):
        """SOC stays within configured bounds."""
        demand_df, solar_df, wind_df, generators_df = default_data
        cfg = Phase2Config(
            enable_battery=True,
            battery_capacity_mwh=400.0, charge_rate_max_mw=100.0,
            discharge_rate_max_mw=100.0, charge_efficiency=0.90,
            discharge_efficiency=0.90, initial_soc_mwh=200.0,
            min_soc_mwh=40.0, max_soc_mwh=360.0,
        )
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        df = result.dispatch_df
        assert df["soc_mwh"].min() >= cfg.min_soc_mwh - 0.01
        assert df["soc_mwh"].max() <= cfg.max_soc_mwh + 0.01

    def test_battery_charge_discharge_bounds(self, default_data):
        """Charge and discharge rates stay within limits."""
        demand_df, solar_df, wind_df, generators_df = default_data
        cfg = Phase2Config(
            enable_battery=True,
            charge_rate_max_mw=100.0, discharge_rate_max_mw=100.0,
            initial_soc_mwh=200.0, min_soc_mwh=40.0, max_soc_mwh=360.0,
        )
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        df = result.dispatch_df
        assert df["charge_mw"].max() <= cfg.charge_rate_max_mw + 0.01
        assert df["discharge_mw"].max() <= cfg.discharge_rate_max_mw + 0.01
        assert df["charge_mw"].min() >= -0.01
        assert df["discharge_mw"].min() >= -0.01

    def test_battery_soc_dynamics(self, default_data):
        """SOC[t] = SOC[t-1] + eta_c*C[t] - D[t]/eta_d."""
        demand_df, solar_df, wind_df, generators_df = default_data
        cfg = Phase2Config(
            enable_battery=True,
            charge_efficiency=0.90, discharge_efficiency=0.90,
            initial_soc_mwh=200.0, min_soc_mwh=40.0, max_soc_mwh=360.0,
        )
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        df = result.dispatch_df.sort_values("hour")
        prev_soc = cfg.initial_soc_mwh
        for _, row in df.iterrows():
            expected = prev_soc + 0.90 * row["charge_mw"] - row["discharge_mw"] / 0.90
            assert abs(row["soc_mwh"] - expected) < 0.01, \
                f"Hour {int(row['hour'])}: SOC {row['soc_mwh']:.3f} != expected {expected:.3f}"
            prev_soc = row["soc_mwh"]

    def test_battery_no_unnecessary_cycling(self, default_data):
        """Without CO2/ramp constraints, battery shouldn't cycle significantly
        since there's no arbitrage opportunity (costs are fixed per source)."""
        demand_df, solar_df, wind_df, generators_df = default_data
        cfg = Phase2Config(
            enable_battery=True, enable_ramp=False, enable_co2_cap=False,
            initial_soc_mwh=40.0, min_soc_mwh=40.0, max_soc_mwh=360.0,
        )
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        # Without cost incentive for storage, total charge should be near zero
        total_charge = result.dispatch_df["charge_mw"].sum()
        total_discharge = result.dispatch_df["discharge_mw"].sum()
        assert total_charge < 1.0, f"Unexpected cycling: charge={total_charge:.2f}"
        assert total_discharge < 1.0, f"Unexpected cycling: discharge={total_discharge:.2f}"

    def test_battery_inter_temporal_with_co2(self, default_data, default_co2_cap):
        """Battery charges earlier and discharges when CO2 cap binds."""
        demand_df, solar_df, wind_df, generators_df = default_data
        cfg = Phase2Config(
            enable_battery=True, enable_co2_cap=True,
            co2_cap_df=default_co2_cap,
            initial_soc_mwh=200.0, min_soc_mwh=40.0, max_soc_mwh=360.0,
        )
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        df = result.dispatch_df
        # There should be some discharge during CO2-capped hours (17-20)
        capped_discharge = df[df["hour"].isin([17, 18, 19, 20])]["discharge_mw"].sum()
        # And some charging before those hours
        pre_charge = df[df["hour"] < 17]["charge_mw"].sum()
        # At least some inter-temporal activity expected
        assert capped_discharge > 0 or pre_charge > 0, "Expected inter-temporal battery activity"

    def test_battery_initial_soc(self, default_data):
        """First hour SOC is based on initial_soc_mwh, not a free variable."""
        demand_df, solar_df, wind_df, generators_df = default_data
        cfg = Phase2Config(
            enable_battery=True,
            initial_soc_mwh=200.0, min_soc_mwh=40.0, max_soc_mwh=360.0,
        )
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        df = result.dispatch_df.sort_values("hour")
        first_row = df.iloc[0]
        expected_soc = 200.0 + 0.90 * first_row["charge_mw"] - first_row["discharge_mw"] / 0.90
        assert abs(first_row["soc_mwh"] - expected_soc) < 0.01


# ============================================================
# Battery Validation Tests
# ============================================================

class TestBatteryValidation:
    def test_valid_battery_config(self):
        """Valid battery config passes validation."""
        cfg = Phase2Config(battery_capacity_mwh=400, charge_rate_max_mw=100,
                          discharge_rate_max_mw=100, charge_efficiency=0.9,
                          discharge_efficiency=0.9, initial_soc_mwh=200,
                          min_soc_mwh=40, max_soc_mwh=360)
        errors = validate_battery_config(cfg)
        assert len(errors) == 0

    def test_invalid_efficiency(self):
        """Efficiency outside (0,1] is rejected."""
        cfg = Phase2Config(charge_efficiency=1.5)
        errors = validate_battery_config(cfg)
        assert any("charge_efficiency" in e for e in errors)

    def test_invalid_initial_soc(self):
        """Initial SOC outside bounds is rejected."""
        cfg = Phase2Config(initial_soc_mwh=500, max_soc_mwh=360)
        errors = validate_battery_config(cfg)
        assert any("initial_soc_mwh" in e for e in errors)


# ============================================================
# Ramp Validation Tests
# ============================================================

class TestRampValidation:
    def test_valid_ramp_config(self):
        """Valid ramp config passes validation."""
        gen_df = pd.DataFrame({
            "source": ["Solar", "Wind", "Thermal"],
            "max_capacity_mw": [400, 300, 800],
            "cost_per_mwh": [10, 15, 85],
            "co2_per_mwh": [0, 0, 820],
        })
        cfg = Phase2Config(ramp_limit_mw_per_hour=200, initial_thermal_output_mw=400)
        errors = validate_ramp_config(cfg, gen_df)
        assert len(errors) == 0

    def test_negative_ramp(self):
        """Negative ramp limit is rejected."""
        gen_df = pd.DataFrame({
            "source": ["Solar", "Wind", "Thermal"],
            "max_capacity_mw": [400, 300, 800],
            "cost_per_mwh": [10, 15, 85],
            "co2_per_mwh": [0, 0, 820],
        })
        cfg = Phase2Config(ramp_limit_mw_per_hour=-10, initial_thermal_output_mw=400)
        errors = validate_ramp_config(cfg, gen_df)
        assert any("ramp_limit" in e for e in errors)

    def test_initial_thermal_exceeds_capacity(self):
        """Initial thermal exceeding capacity is rejected."""
        gen_df = pd.DataFrame({
            "source": ["Solar", "Wind", "Thermal"],
            "max_capacity_mw": [400, 300, 800],
            "cost_per_mwh": [10, 15, 85],
            "co2_per_mwh": [0, 0, 820],
        })
        cfg = Phase2Config(ramp_limit_mw_per_hour=200, initial_thermal_output_mw=900)
        errors = validate_ramp_config(cfg, gen_df)
        assert any("initial_thermal" in e.lower() for e in errors)


# ============================================================
# Reliability Mode Tests
# ============================================================

class TestReliabilityMode:
    def test_strict_mode_infeasible(self, default_data):
        """Strict mode reports infeasibility when CO2 cap is too tight."""
        demand_df, solar_df, wind_df, generators_df = default_data
        co2_cap_df = pd.DataFrame({
            "hour": list(range(24)),
            "co2_cap_kg": [1.0] * 24,
        })
        cfg = Phase2Config(enable_co2_cap=True, co2_cap_df=co2_cap_df,
                          enable_reliability=False)
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Infeasible"

    def test_reliability_mode_with_unmet(self, default_data):
        """Reliability mode solves with unmet demand when constraints are very tight."""
        demand_df, solar_df, wind_df, generators_df = default_data
        co2_cap_df = pd.DataFrame({
            "hour": list(range(24)),
            "co2_cap_kg": [1.0] * 24,  # Forces almost all thermal to zero
        })
        cfg = Phase2Config(
            enable_co2_cap=True, co2_cap_df=co2_cap_df,
            enable_reliability=True, unmet_demand_penalty=50000.0,
        )
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        assert result.total_unmet_demand > 0

    def test_unmet_demand_penalized(self, default_data):
        """Unmet demand increases cost significantly."""
        demand_df, solar_df, wind_df, generators_df = default_data
        co2_cap_df = pd.DataFrame({
            "hour": list(range(24)),
            "co2_cap_kg": [1.0] * 24,
        })
        cfg = Phase2Config(
            enable_co2_cap=True, co2_cap_df=co2_cap_df,
            enable_reliability=True, unmet_demand_penalty=50000.0,
        )
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        # Total cost should be much higher than baseline due to penalty
        baseline = solve_dispatch(demand_df, solar_df, wind_df, generators_df)
        assert result.total_cost > baseline.total_cost * 2


# ============================================================
# Integrated Model Tests
# ============================================================

class TestIntegratedModel:
    def test_full_model_demand_balance(self, default_data, default_co2_cap):
        """Full model with all features maintains demand balance."""
        demand_df, solar_df, wind_df, generators_df = default_data
        cfg = Phase2Config(
            enable_ramp=True, ramp_limit_mw_per_hour=200.0,
            initial_thermal_output_mw=400.0,
            enable_co2_cap=True, co2_cap_df=default_co2_cap,
            enable_battery=True,
            initial_soc_mwh=200.0, min_soc_mwh=40.0, max_soc_mwh=360.0,
        )
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        df = result.dispatch_df
        for _, row in df.iterrows():
            net = row["solar_mw"] + row["wind_mw"] + row["thermal_mw"] + \
                  row["discharge_mw"] - row["charge_mw"]
            assert abs(net - row["demand_mw"]) < 0.01, \
                f"Hour {int(row['hour'])}: demand balance violated"

    def test_full_model_no_nan(self, default_data, default_co2_cap):
        """No NaN values in the dispatch DataFrame."""
        demand_df, solar_df, wind_df, generators_df = default_data
        cfg = Phase2Config(
            enable_ramp=True, enable_co2_cap=True, co2_cap_df=default_co2_cap,
            enable_battery=True,
            initial_soc_mwh=200.0, min_soc_mwh=40.0, max_soc_mwh=360.0,
        )
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        assert not result.dispatch_df.isna().any().any()

    def test_full_model_verified(self, default_data, default_co2_cap):
        """Full model passes post-solve verification."""
        demand_df, solar_df, wind_df, generators_df = default_data
        cfg = Phase2Config(
            enable_ramp=True, ramp_limit_mw_per_hour=200.0,
            initial_thermal_output_mw=400.0,
            enable_co2_cap=True, co2_cap_df=default_co2_cap,
            enable_battery=True,
            initial_soc_mwh=200.0, min_soc_mwh=40.0, max_soc_mwh=360.0,
        )
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        assert result.is_verified

    def test_full_model_shadow_prices_present(self, default_data, default_co2_cap):
        """Full model with all features still extracts shadow prices."""
        demand_df, solar_df, wind_df, generators_df = default_data
        cfg = Phase2Config(
            enable_ramp=True, enable_co2_cap=True, co2_cap_df=default_co2_cap,
            enable_battery=True,
            initial_soc_mwh=200.0, min_soc_mwh=40.0, max_soc_mwh=360.0,
        )
        result = solve_dispatch(demand_df, solar_df, wind_df, generators_df, cfg)
        assert result.status == "Optimal"
        assert result.shadow_prices is not None
        assert len(result.shadow_prices) == 24
        for sp in result.shadow_prices.values():
            assert np.isfinite(sp)
