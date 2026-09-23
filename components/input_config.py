import streamlit as st
import pandas as pd
from src.data_loader import load_default_data, DataBundle
from src.validation import validate_data

def render_input_config() -> DataBundle:
    """Render input configuration page. Returns validated DataBundle."""
    st.header("⚙️ Input Configuration")

    data_source = st.radio(
        "Select data source:",
        ["Default Dataset", "Upload Custom CSVs"],
        horizontal=True,
    )

    bundle = None

    if data_source == "Default Dataset":
        st.info("Using bundled 24-hour synthetic demonstration dataset.")
        bundle = load_default_data()
        # Show preview tables
        with st.expander("📋 Demand Data (first 6 hours)"):
            st.dataframe(bundle.demand_df.head(6), use_container_width=True)
        with st.expander("📋 Solar Availability (first 6 hours)"):
            st.dataframe(bundle.solar_df.head(6), use_container_width=True)
        with st.expander("📋 Wind Availability (first 6 hours)"):
            st.dataframe(bundle.wind_df.head(6), use_container_width=True)
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
