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

    infeasible_hours = []
    for _, row in demand_df.iterrows():
        h = int(row["hour"])
        demand = float(row["demand_mw"])
        solar_avail = float(solar_df[solar_df["hour"] == h]["solar_available_mw"].values[0])
        wind_avail = float(wind_df[wind_df["hour"] == h]["wind_available_mw"].values[0])
        max_gen = solar_avail + wind_avail + thermal_capacity
        if max_gen < demand - 1e-6:
            infeasible_hours.append({
                "hour": h,
                "demand": demand,
                "max_available": max_gen,
                "shortfall": demand - max_gen,
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
    invalid = df[~df[col].isin(range(24))]
    if not invalid.empty:
        bad = invalid[col].tolist()
        errors.append(f"{name}: Hour values must be 0-23. Found: {bad}")
        
    # Check for complete 0-23 hour set (missing hours)
    expected_hours = set(range(24))
    actual_hours = set(df[col].dropna().astype(int))
    missing_hours = expected_hours - actual_hours
    if missing_hours:
        errors.append(f"{name}: Missing hours in dataset: {sorted(list(missing_hours))}")
        
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
