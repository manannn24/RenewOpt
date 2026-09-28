from dataclasses import dataclass, field
from typing import List
import pandas as pd

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

def validate_data(demand_df, solar_df, wind_df, generators_df) -> ValidationResult:
    """
    Validate all input DataFrames before optimization.
    Returns ValidationResult with errors/warnings.
    """
    errors = []
    warnings = []

    # --- demand.csv ---
    demand_col_errors = _check_columns(demand_df, ["hour", "demand_mw"], "demand")
    errors += demand_col_errors
    if not demand_col_errors:
        demand_num_errors = _check_numeric(demand_df, "demand_mw", "demand")
        errors += demand_num_errors
        if not demand_num_errors:
            errors += _check_hours(demand_df, "hour", "demand")
            errors += _check_non_negative(demand_df, "demand_mw", "demand_mw")
            errors += _check_no_missing(demand_df, ["hour", "demand_mw"], "demand")
            errors += _check_no_duplicates(demand_df, "hour", "demand")

    # --- solar_availability.csv ---
    solar_col_errors = _check_columns(solar_df, ["hour", "solar_available_mw"], "solar_availability")
    errors += solar_col_errors
    if not solar_col_errors:
        solar_num_errors = _check_numeric(solar_df, "solar_available_mw", "solar_availability")
        errors += solar_num_errors
        if not solar_num_errors:
            errors += _check_hours(solar_df, "hour", "solar_availability")
            errors += _check_non_negative(solar_df, "solar_available_mw", "solar_available_mw")
            errors += _check_no_missing(solar_df, ["hour", "solar_available_mw"], "solar_availability")
            errors += _check_no_duplicates(solar_df, "hour", "solar_availability")

    # --- wind_availability.csv ---
    wind_col_errors = _check_columns(wind_df, ["hour", "wind_available_mw"], "wind_availability")
    errors += wind_col_errors
    if not wind_col_errors:
        wind_num_errors = _check_numeric(wind_df, "wind_available_mw", "wind_availability")
        errors += wind_num_errors
        if not wind_num_errors:
            errors += _check_hours(wind_df, "hour", "wind_availability")
            errors += _check_non_negative(wind_df, "wind_available_mw", "wind_available_mw")
            errors += _check_no_missing(wind_df, ["hour", "wind_available_mw"], "wind_availability")
            errors += _check_no_duplicates(wind_df, "hour", "wind_availability")

    # --- generators.csv ---
    gen_col_errors = _check_columns(
        generators_df,
        ["source", "max_capacity_mw", "cost_per_mwh", "co2_per_mwh"],
        "generators",
    )
    errors += gen_col_errors
    if not gen_col_errors:
        gen_num_errors = _check_numeric(generators_df, "max_capacity_mw", "generators")
        gen_num_errors += _check_numeric(generators_df, "cost_per_mwh", "generators")
        gen_num_errors += _check_numeric(generators_df, "co2_per_mwh", "generators")
        errors += gen_num_errors
        if not gen_num_errors:
            errors += _check_non_negative(generators_df, "max_capacity_mw", "max_capacity_mw")
            errors += _check_non_negative(generators_df, "cost_per_mwh", "cost_per_mwh")
            errors += _check_non_negative(generators_df, "co2_per_mwh", "co2_per_mwh")
            errors += _check_positive(generators_df, "max_capacity_mw", "max_capacity_mw")
            errors += _check_required_sources(generators_df)
            errors += _check_unique_sources(generators_df)

    # --- availability vs capacity (only when all prior checks pass) ---
    if not errors:
        # Convert to numeric safely for the capacity check since we passed validation
        # But wait, did we convert in place? No, we just validated. We should make sure the comparison works, 
        # but if it passed _check_numeric, it might still be a string like "100.0". 
        # We will handle the type coercion inside `_check_availability_vs_capacity` if needed, 
        # but Pandas usually handles string to float if it parses, though it's better if it's float.
        # Actually, let's just make sure the check passes.
        errors += _check_availability_vs_capacity(solar_df, generators_df, "Solar", "solar_available_mw")
        errors += _check_availability_vs_capacity(wind_df, generators_df, "Wind", "wind_available_mw")

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)



def check_feasibility(demand_df, solar_df, wind_df, generators_df):
    """
    Check hourly feasibility: solar_available + wind_available + thermal_capacity >= demand.
    Returns list of infeasible hour details.
    """
    thermal_row = generators_df[generators_df["source"] == "Thermal"]
    thermal_capacity = float(thermal_row["max_capacity_mw"].values[0])

    # Vectorized operations for speed on 8,760-hour datasets
    df = demand_df.copy()
    
    # Align hours to ensure correct merging
    solar_mapped = solar_df.set_index("hour")["solar_available_mw"]
    wind_mapped = wind_df.set_index("hour")["wind_available_mw"]
    
    df["solar_avail"] = df["hour"].map(solar_mapped)
    df["wind_avail"] = df["hour"].map(wind_mapped)
    
    df["max_gen"] = df["solar_avail"] + df["wind_avail"] + thermal_capacity
    df["shortfall"] = df["demand_mw"] - df["max_gen"]
    
    # Filter infeasible hours
    infeasible = df[df["shortfall"] > 1e-6]
    
    infeasible_hours = []
    for _, row in infeasible.iterrows():
        infeasible_hours.append({
            "hour": int(row["hour"]),
            "demand": float(row["demand_mw"]),
            "max_available": float(row["max_gen"]),
            "shortfall": float(row["shortfall"]),
        })
    return infeasible_hours


# --- helper functions ---

def _check_numeric(df, col, name):
    errors = []
    if col not in df.columns:
        return errors
    if pd.api.types.is_numeric_dtype(df[col]):
        return errors
    
    original_non_null = df[col].dropna()
    converted = pd.to_numeric(original_non_null, errors='coerce')
    bad_values = original_non_null[converted.isna()]
    
    if not bad_values.empty:
        errors.append(f"{name}: Column '{col}' contains non-numeric values (e.g., '{bad_values.iloc[0]}').")
    else:
        # Convert in-place so downstream arithmetic works on valid numeric strings
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return errors

def _check_columns(df, required_cols, name):
    errors = []
    for col in required_cols:
        if col not in df.columns:
            errors.append(f"{name}: Missing required column '{col}'.")
    return errors

def _check_hours(df, col, name):
    errors = []
    if col not in df.columns:
        return errors
    if not pd.api.types.is_numeric_dtype(df[col]):
        errors.append(f"{name}: Column '{col}' must be numeric.")
        return errors
        
    # Check for out-of-range hours (extra/invalid)
    num_rows = len(df)
    valid_range = set(range(num_rows))
    
    invalid = df[~df[col].isin(valid_range)]
    if not invalid.empty:
        # Just report first few if there are many
        bad = invalid[col].head(5).tolist()
        errors.append(f"{name}: Hour values must be 0-{num_rows-1}. Found out of range: {bad}...")
        
    # Check for complete sequence (missing hours)
    actual_hours = set(df[col].dropna().astype(int))
    missing_hours = valid_range - actual_hours
    if missing_hours:
        missing_sample = sorted(list(missing_hours))[:5]
        errors.append(f"{name}: Missing hours in dataset ({len(missing_hours)}). E.g., {missing_sample}...")
        
    return errors

def _check_non_negative(df, col, label):
    errors = []
    if col not in df.columns:
        return errors
    neg = df[df[col] < 0]
    if not neg.empty:
        errors.append(f"Column '{label}' contains negative values.")
    return errors

def _check_positive(df, col, label):
    errors = []
    if col not in df.columns:
        return errors
    zero = df[df[col] <= 0]
    if not zero.empty:
        errors.append(f"Column '{label}' must be > 0 for all generators.")
    return errors

def _check_no_missing(df, cols, name):
    errors = []
    for col in cols:
        if col in df.columns and df[col].isnull().any():
            errors.append(f"{name}: Column '{col}' has missing values.")
    return errors

def _check_no_duplicates(df, col, name):
    errors = []
    if col not in df.columns:
        return errors
    if df[col].duplicated().any():
        dupes = df[col][df[col].duplicated()].tolist()
        errors.append(f"{name}: Duplicate hours found: {dupes}")
    return errors

def _check_required_sources(generators_df):
    errors = []
    sources = generators_df["source"].tolist()
    for required in ["Solar", "Wind", "Thermal"]:
        if required not in sources:
            errors.append(f"generators: Required source '{required}' is missing.")
    return errors

def _check_unique_sources(generators_df):
    errors = []
    if generators_df["source"].duplicated().any():
        errors.append("generators: Duplicate source names found.")
    return errors

def _check_availability_vs_capacity(avail_df, generators_df, source_name, avail_col):
    errors = []
    row = generators_df[generators_df["source"] == source_name]
    if row.empty:
        return errors
    capacity = float(row["max_capacity_mw"].values[0])
    if avail_col in avail_df.columns:
        exceeded = avail_df[avail_df[avail_col] > capacity + 1e-6]
        if not exceeded.empty:
            max_avail = avail_df[avail_col].max()
            errors.append(
                f"{source_name} availability ({max_avail:.1f} MW) exceeds installed capacity ({capacity:.1f} MW) in {len(exceeded)} hour(s)."
            )
    return errors


def validate_co2_cap(co2_cap_df):
    """Validate co2_cap.csv data. Returns list of error strings."""
    errors = []
    if co2_cap_df is None:
        errors.append("co2_cap: DataFrame is None.")
        return errors
    col_errors = _check_columns(co2_cap_df, ["hour", "co2_cap_kg"], "co2_cap")
    errors += col_errors
    if col_errors:
        return errors
    num_errors = _check_numeric(co2_cap_df, "co2_cap_kg", "co2_cap")
    errors += num_errors
    if num_errors:
        return errors
    errors += _check_hours(co2_cap_df, "hour", "co2_cap")
    errors += _check_non_negative(co2_cap_df, "co2_cap_kg", "co2_cap_kg")
    errors += _check_no_missing(co2_cap_df, ["hour", "co2_cap_kg"], "co2_cap")
    errors += _check_no_duplicates(co2_cap_df, "hour", "co2_cap")
    return errors


def validate_battery_config(cfg):
    """Validate Phase2Config battery parameters. Returns list of error strings."""
    errors = []
    if cfg.battery_capacity_mwh <= 0:
        errors.append("battery: capacity_mwh must be > 0.")
    if cfg.charge_rate_max_mw <= 0:
        errors.append("battery: charge_rate_max_mw must be > 0.")
    if cfg.discharge_rate_max_mw <= 0:
        errors.append("battery: discharge_rate_max_mw must be > 0.")
    if not (0 < cfg.charge_efficiency <= 1):
        errors.append("battery: charge_efficiency must be in (0, 1].")
    if not (0 < cfg.discharge_efficiency <= 1):
        errors.append("battery: discharge_efficiency must be in (0, 1].")
    if cfg.min_soc_mwh < 0:
        errors.append("battery: min_soc_mwh must be >= 0.")
    if cfg.max_soc_mwh <= cfg.min_soc_mwh:
        errors.append("battery: max_soc_mwh must be > min_soc_mwh.")
    if cfg.max_soc_mwh > cfg.battery_capacity_mwh:
        errors.append("battery: max_soc_mwh must be <= capacity_mwh.")
    if cfg.initial_soc_mwh < cfg.min_soc_mwh:
        errors.append("battery: initial_soc_mwh must be >= min_soc_mwh.")
    if cfg.initial_soc_mwh > cfg.max_soc_mwh:
        errors.append("battery: initial_soc_mwh must be <= max_soc_mwh.")
    return errors


def validate_ramp_config(cfg, generators_df):
    """Validate Phase2Config ramp parameters. Returns list of error strings."""
    errors = []
    if cfg.ramp_limit_mw_per_hour <= 0:
        errors.append("ramp: ramp_limit_mw_per_hour must be > 0.")
    thermal_row = generators_df[generators_df["source"] == "Thermal"]
    if not thermal_row.empty:
        thermal_capacity = float(thermal_row["max_capacity_mw"].values[0])
        if cfg.initial_thermal_output_mw < 0:
            errors.append("ramp: initial_thermal_output_mw must be >= 0.")
        if cfg.initial_thermal_output_mw > thermal_capacity:
            errors.append(f"ramp: initial_thermal_output_mw ({cfg.initial_thermal_output_mw}) must be <= thermal capacity ({thermal_capacity}).")
    return errors
