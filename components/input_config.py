import streamlit as st
import pandas as pd
from src.data_loader import load_default_data, load_8760_data, DataBundle
from src.validation import validate_data

def render_input_config() -> DataBundle:
    """Render input configuration page. Returns validated DataBundle."""
    st.header("⚙️ Input Configuration")

    data_source = st.radio(
        "Select data source:",
        ["Default Dataset (24 hours)", "Full Year Dataset (8760 hours)", "Upload Custom CSVs"],
        horizontal=True,
    )

    bundle = None

    if data_source == "Default Dataset (24 hours)":
        st.info("Using bundled 24-hour synthetic demonstration dataset.")
        bundle = load_default_data()
    elif data_source == "Full Year Dataset (8760 hours)":
        st.info("Using full-year 8,760-hour dataset. Optimization may take a few moments.")
        bundle = load_8760_data()
        
    if data_source in ["Default Dataset (24 hours)", "Full Year Dataset (8760 hours)"]:
        is_8760 = (data_source == "Full Year Dataset (8760 hours)")
        
        st.subheader("📊 Data Explorer")
        
        # Helper to join the three dataframes
        @st.cache_data
        def get_joined_data(demand, solar, wind):
            df = demand.copy()
            df["solar_available_mw"] = solar["solar_available_mw"]
            df["wind_available_mw"] = wind["wind_available_mw"]
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            return df

        joined_df = get_joined_data(bundle.demand_df, bundle.solar_df, bundle.wind_df)

        if not is_8760:
            st.dataframe(joined_df, use_container_width=True)
        else:
            view_mode = st.radio("Select View:", ["Monthly", "Date Range", "Single Day"], horizontal=True)
            
            if "timestamp" not in joined_df.columns:
                st.warning("Timestamp column missing. Displaying first 100 rows.")
                st.dataframe(joined_df.head(100), use_container_width=True)
            else:
                if view_mode == "Monthly":
                    months = joined_df["timestamp"].dt.strftime('%B %Y').unique()
                    selected_month = st.selectbox("Select Month", months)
                    mask = joined_df["timestamp"].dt.strftime('%B %Y') == selected_month
                    view_df = joined_df[mask]
                    st.caption(f"Showing {len(view_df)} hourly records for {selected_month}")
                    st.dataframe(view_df, use_container_width=True, height=400)
                    
                elif view_mode == "Date Range":
                    min_date = joined_df["timestamp"].min().date()
                    max_date = joined_df["timestamp"].max().date()
                    dates = st.date_input("Select Date Range", [min_date, max_date], min_value=min_date, max_value=max_date)
                    if len(dates) == 2:
                        start_date, end_date = dates
                        mask = (joined_df["timestamp"].dt.date >= start_date) & (joined_df["timestamp"].dt.date <= end_date)
                        view_df = joined_df[mask]
                        st.caption(f"Showing {len(view_df)} hourly records from {start_date} to {end_date}")
                        st.dataframe(view_df, use_container_width=True, height=400)
                    else:
                        st.info("Please select a valid date range.")
                        
                elif view_mode == "Single Day":
                    min_date = joined_df["timestamp"].min().date()
                    max_date = joined_df["timestamp"].max().date()
                    selected_date = st.date_input("Select Date", min_date, min_value=min_date, max_value=max_date)
                    mask = joined_df["timestamp"].dt.date == selected_date
                    view_df = joined_df[mask]
                    st.caption(f"Showing {len(view_df)} hourly records for {selected_date}")
                    st.dataframe(view_df, use_container_width=True, height=400)

        with st.expander("📋 Generator Parameters"):
            st.dataframe(bundle.generators_df, use_container_width=True)

    else:  # Upload
        st.markdown("Upload four CSV files matching the required schema:")
        col1, col2 = st.columns(2)
        with col1:
            demand_file = st.file_uploader("demand.csv (hour, demand_mw)", type="csv", key="demand_upload")
            solar_file = st.file_uploader("solar_availability.csv (hour, solar_available_mw)", type="csv", key="solar_upload")
        with col2:
            wind_file = st.file_uploader("wind_availability.csv (hour, wind_available_mw)", type="csv", key="wind_upload")
            gen_file = st.file_uploader("generators.csv (source, max_capacity_mw, cost_per_mwh, co2_per_mwh)", type="csv", key="gen_upload")

        if all([demand_file, solar_file, wind_file, gen_file]):
            try:
                from src.data_loader import load_from_uploads
                bundle = load_from_uploads(demand_file, solar_file, wind_file, gen_file)
                st.success("All files uploaded successfully.")
            except Exception as e:
                st.error(f"Error reading uploaded files: {e}")
                return None
        else:
            st.warning("Please upload all four CSV files.")
            return None

    # --- Generator parameter editor ---
    if bundle is not None:
        st.subheader("✏️ Edit Generator Parameters")
        st.caption("Modify generator capacity, cost, or emission factors. Changes will trigger a fresh optimization.")
        edited_gen = st.data_editor(
            bundle.generators_df,
            use_container_width=True,
            num_rows="fixed",
            key="gen_editor",
        )
        bundle = DataBundle(
            demand_df=bundle.demand_df,
            solar_df=bundle.solar_df,
            wind_df=bundle.wind_df,
            generators_df=edited_gen,
            co2_cap_df=bundle.co2_cap_df,
            battery_df=bundle.battery_df,
        )

        # Validate
        validation = validate_data(
            bundle.demand_df, bundle.solar_df, bundle.wind_df, bundle.generators_df
        )
        if not validation.is_valid:
            for err in validation.errors:
                st.error(f"❌ {err}")
            return None
        else:
            st.success("✅ Input data validated successfully.")

    return bundle
