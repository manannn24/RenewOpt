import pytest
import pandas as pd
from src.data_loader import load_8760_data, build_phase2_config
from src.optimizer import solve_dispatch
from src.validation import validate_data
from src.calculations import build_metrics

def test_8760_data_validation():
    b = load_8760_data()
    v = validate_data(b.demand_df, b.solar_df, b.wind_df, b.generators_df)
    assert v.is_valid, "Baseline 8760 data should be valid"
    
def test_8760_missing_timestamp():
    b = load_8760_data()
    # drop an intermediate row
    b.demand_df = b.demand_df.drop(50).reset_index(drop=True)
    v = validate_data(b.demand_df, b.solar_df, b.wind_df, b.generators_df)
    assert not v.is_valid
    assert any("sequential" in err.lower() or "missing" in err.lower() or "length" in err.lower() for err in v.errors)

def test_8760_missing_and_duplicate_timestamp():
    b = load_8760_data()
    # duplicate row 10, drop row 50, so length is still 8760
    df = b.demand_df.copy()
    row_10 = df.iloc[[10]]
    df = pd.concat([df.iloc[:50], df.iloc[51:], row_10]).reset_index(drop=True)
    b.demand_df = df
    v = validate_data(b.demand_df, b.solar_df, b.wind_df, b.generators_df)
    assert not v.is_valid
    assert any("duplicate" in err.lower() for err in v.errors)

def test_8760_monthly_reconciliation():
    b = load_8760_data()
    cfg = build_phase2_config(b, {"enable_battery": True, "enable_reliability": True})
    res = solve_dispatch(b.demand_df, b.solar_df, b.wind_df, b.generators_df, cfg)
    
    df = res.dispatch_df
    annual_gen = df["thermal_mw"].sum() + df["solar_mw"].sum() + df["wind_mw"].sum()
    
    # Monthly aggregate
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["month"] = df["timestamp"].dt.to_period("M")
    monthly = df.groupby("month")[["thermal_mw", "solar_mw", "wind_mw"]].sum()
    monthly_gen = monthly.sum().sum()
    
    assert abs(annual_gen - monthly_gen) < 1e-4

def test_battery_temporal_correctness():
    b = load_8760_data()
    # Tiny horizon for speed
    b.demand_df = b.demand_df.head(48).copy()
    b.solar_df = b.solar_df.head(48).copy()
    b.wind_df = b.wind_df.head(48).copy()
    
    cfg = build_phase2_config(b, {"enable_battery": True})
    cfg.initial_soc_mwh = 200.0
    res = solve_dispatch(b.demand_df, b.solar_df, b.wind_df, b.generators_df, cfg)
    
    df = res.dispatch_df
    # Check hour 1 depends on hour 0
    soc_0 = df.loc[0, "soc_mwh"]
    soc_1 = df.loc[1, "soc_mwh"]
    chg_1 = df.loc[1, "charge_mw"]
    dis_1 = df.loc[1, "discharge_mw"]
    
    expected_soc_1 = soc_0 + cfg.charge_efficiency * chg_1 - dis_1 / cfg.discharge_efficiency
    assert abs(soc_1 - expected_soc_1) < 1e-4
