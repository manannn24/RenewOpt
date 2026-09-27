# RenewOpt: Renewable Energy Grid Dispatch Optimization

## 1. Core Problem Statement

The electrical grid must continuously balance supply and demand. Integrating large amounts of variable renewable energy (VRE) like Solar and Wind creates significant operational challenges. 

Grid operators need an **Operations Research (OR) model** to determine the most cost-effective and reliable way to dispatch power across a **Full-Year (8,760-hour) planning horizon**.

**RenewOpt solves the Economic Dispatch Problem** using Linear Programming (LP). The objective is to:
1. **Minimize total generation cost** across a full year (8,760 hours).
2. **Maximize renewable energy utilization**.
3. **Satisfy continuous demand** while respecting capacity, availability, emission limits, and battery dynamics.

---

## 2. Linear Programming Formulation

The core optimization is formulated as a linear program and solved using the **CBC solver** via the **PuLP** Python library.

### Sets & Indices
- $t \in \{0, 1, ..., 8759\}$: Planning horizon periods (1 hour each).

### Decision Variables (Continuous)
- $S_t$: Solar power dispatched at hour $t$ (MWh)
- $W_t$: Wind power dispatched at hour $t$ (MWh)
- $T_t$: Thermal power dispatched at hour $t$ (MWh)
- $C_t$: Battery charging power at hour $t$ (MWh)
- $D_t$: Battery discharging power at hour $t$ (MWh)
- $SOC_t$: Battery State of Charge at hour $t$ (MWh)
- $Unmet_t$: Unmet demand (slack variable for reliability mode) at hour $t$ (MWh)

### Objective Function
Minimize the total annual system cost, including an extreme penalty for unmet demand:
$$ \text{Minimize } Z = \sum_{t=0}^{8759} \left( C_s \cdot S_t + C_w \cdot W_t + C_{th} \cdot T_t + P_{unmet} \cdot Unmet_t \right) $$

### Constraints

**1. Demand Balance** (The fundamental grid equation):
$$ S_t + W_t + T_t + D_t - C_t + Unmet_t = \text{Demand}_t \quad \forall t $$

**2. Renewable Availability** (Upper bounds based on weather):
$$ 0 \leq S_t \leq \text{SolarAvail}_t \quad \forall t $$
$$ 0 \leq W_t \leq \text{WindAvail}_t \quad \forall t $$

**3. Thermal Capacity & Ramping** (Generator physics):
$$ 0 \leq T_t \leq \text{ThermalCap} \quad \forall t $$
$$ |T_t - T_{t-1}| \leq \text{RampLimit} \quad \forall t $$

**4. Hourly CO₂ Emissions Cap** (Environmental policy):
$$ T_t \cdot \text{CO2Factor}_{th} \leq \text{CO2Cap}_t \quad \forall t $$

**5. Battery Dynamics** (Energy storage inter-temporal linkage):
$$ SOC_t = SOC_{t-1} + \eta_{charge} C_t - \frac{D_t}{\eta_{discharge}} \quad \forall t $$
$$ \text{MinSOC} \leq SOC_t \leq \text{MaxCapacity} \quad \forall t $$
$$ 0 \leq C_t \leq \text{MaxChargeRate}, \quad 0 \leq D_t \leq \text{MaxDischargeRate} \quad \forall t $$

---

## 3. Features

### Core OR Features
- **Deterministic Linear Programming (LP)** over arbitrary time horizons (supports 24h demo up to 8,760h full year).
- Inter-temporal battery energy storage optimization (Charge, Discharge, State-of-Charge).
- Thermal ramp-rate limitations (forces pre-positioning).
- Hourly CO₂ emission caps.
- **Reliability Mode (Soft Constraints)**: Uses high-penalty slack variables to identify when constraints must be broken, rather than simply reporting "Infeasible".
- **Shadow Pricing**: Extracts the dual values (shadow prices) of the demand-balance constraint to represent the marginal cost of electricity (₹/MWh) for every hour of the year.

### Metrics & Analytics
- Total minimum generation cost, Renewable share, Thermal dependency
- CO₂ emissions (kg) by source and total
- Source-wise cost breakdown
- Hourly Shadow Prices (Marginal Cost)
- Battery state of charge (SOC) dynamics
- **Monthly Aggregation**: Converts 8,760 hourly data points into comprehensive monthly generation and emission metrics.

### Scenario Analysis
- **Phase 1 Scenarios**: Baseline, High Demand, Low Solar, High Thermal Cost, Increased Renewable
- **Phase 2 Scenarios**: Extended Baseline, Tight Evening CO₂ Cap, Tight CO₂ + Battery, Insufficient Battery, Tight Ramp, Relaxed Ramp, Battery Arbitrage Only

### UI (Streamlit)
- Dashboard with 4 core KPIs and 4 advanced Phase 2 metrics, plus a Monthly Analysis summary for full-year datasets.
- Input Configuration to switch between 24h demo and 8,760h datasets.
- Optimization page with Phase 2 feature toggles and mathematical formulation.
- Results page with interactive Plotly area/scatter charts (using dataset timestamps).
- Scenario Analysis with Phase 1 vs Phase 2 comparative analysis.

---

## 4. Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.x |
| Optimization | PuLP |
| Solver | CBC (via PuLP) |
| Data Processing | Pandas, NumPy |
| Visualization | Plotly |
| Frontend | Streamlit |
| Testing | pytest |
| Data Storage | CSV |

---

## 5. Installation

### Prerequisites
- Python 3.8 or higher
- pip

### Setup

```bash
# Clone or download the project
cd RenewOpt

# (Recommended) Create a virtual environment
python -m venv .venv

# Windows activation
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## 6. How to Run

### Start the Application

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`.

### Recommended Demo Flow

1. **Input Configuration** → Select **Full Year Dataset (8760 hours)**
2. **Optimization** → Toggle Phase 2 Advanced Options → Run LP
3. **Results** → View dispatch table, Battery SOC, Shadow Prices, and **Monthly Aggregation**
4. **Scenario Analysis** → Select scenarios → Compare long-term impacts

### Run Tests

```bash
python -m pytest tests/ -v -W ignore::DeprecationWarning
```

### Run Standalone Verification

```bash
python verify_lp.py
```

---

## 7. Dataset Schema

### `data_8760/` (Full-Year Data)
The system supports full-year chronologically ordered hourly data.

| File | Structure |
|---|---|
| `demand.csv` | `timestamp, hour_of_day, demand_mw` |
| `solar_availability.csv`| `timestamp, hour_of_day, solar_available_mw` |
| `wind_availability.csv` | `timestamp, hour_of_day, wind_available_mw` |
| `generators.csv` | `source, max_capacity_mw, cost_per_mwh, co2_per_mwh` |

### Auxiliary Configs
- `data/battery.csv`: Battery storage specifications (capacity, rates, efficiencies).
- `data/co2_cap.csv`: (Optional) Hourly emission caps for the 24-hour demo.

---

## 8. Default Dataset Assumptions

This project includes both a 24-hour demo dataset and a massive synthetic 8,760-hour full-year dataset.

### Phase 2 Configurations
- **Battery**: 400 MWh capacity, 100 MW charge/discharge rate, 90% efficiency.
- **Ramp Limit**: 200 MW/hr for Thermal generator.
- **CO₂ Cap**: Can be enabled via UI to demonstrate inter-temporal battery pre-positioning.

---

## 9. Project Structure

```
RenewOpt/
├── app.py                          # Streamlit entry point
├── data/                           # 24-hour demo dataset
├── data_8760/                      # 8,760-hour full-year dataset
│   ├── demand.csv
│   ├── solar_availability.csv
│   ├── wind_availability.csv
│   └── generators.csv
├── src/
│   ├── data_loader.py              # Load datasets (24h/8760h)
│   ├── validation.py               # Input validation layer
│   ├── optimizer.py                # Core LP formulation
│   ├── calculations.py             # Derived metrics
│   └── scenarios.py                # Scenario definitions
├── components/
│   ├── dashboard.py                # Dashboard KPI page
│   ├── input_config.py             # Input configuration
│   ├── results.py                  # Results + monthly charts page
│   └── scenario_analysis.py        # Scenario comparison page
├── tests/                          # 62 unit & integration tests
├── verify_lp.py                    # Standalone mathematical verification
├── requirements.txt
├── README.md
└── .gitignore
```

---

## 10. Automated Tests

- `test_validation.py`: 11 tests
- `test_optimizer.py`: 8 tests
- `test_calculations.py`: 7 tests
- `test_phase2.py`: 36 tests

**Total: 62 tests**

**Verified result: 62/62 tests passing on the Phase 2 LP Model.**

---

## 11. Limitations

- **No transmission**: Single-node model; no network constraints
- **Deterministic**: Renewable availability is fixed (no stochastic uncertainty)
- **Synthetic data**: Datasets are not real-world grid measurements
- **No unit commitment**: On/off decisions not modeled (LP only, no integer variables)
- **No AC power flow**: Electrical engineering constraints not modeled

---

## 12. Future Scope

- Stochastic optimization for uncertain renewable availability
- Multi-objective optimization (cost vs. emissions trade-off with Pareto frontier)
- Transmission network constraints (DC power flow)
- Multi-node dispatch
- Machine learning demand forecasting
- Real-time data integration (e.g., POSOCO/NPP APIs)

---

## 13. References and Data Sources

- **PuLP Documentation**: https://coin-or.github.io/pulp/
- **CBC Solver**: https://github.com/coin-or/Cbc

> **Data Attribution:** All numerical values in `data/` and `data_8760/` are **synthetic and project-generated**. They are suitable for academic demonstration only.
