# RenewOpt: Renewable Energy Grid Dispatch Optimization

**Operations Research Mini-Project** | **Linear Programming** | **Streamlit + PuLP + CBC**

---

## 1. Project Overview

**RenewOpt** is a Linear Programming-based decision-support system that determines the optimal hourly
electricity generation mix from Solar, Wind, and Thermal sources to satisfy a 24-hour demand profile
at minimum total generation cost, while respecting all generation capacity and renewable availability
constraints.

This project is an academic Operations Research mini-project demonstrating:
- LP formulation and correctness
- PuLP + CBC solver integration
- Scenario-based sensitivity analysis
- Interactive Streamlit dashboard

---

## 2. Problem Statement

Modern electricity grids combine conventional and renewable generation sources that differ in cost,
capacity, availability, and environmental impact.

> **Given** hourly electricity demand and the availability, capacity, generation cost, and emission
> characteristics of Solar, Wind, and Thermal generators, **determine** the optimal amount of
> electricity to generate from each source in every time interval so that demand is satisfied at
> **minimum total generation cost**.

---

## 3. OR Formulation (Linear Programming)

### Decision Variables

For each hour $t = 0, 1, \ldots, 23$:

- $S_t$ = Solar generation (MWh)
- $W_t$ = Wind generation (MWh)
- $T_t$ = Thermal generation (MWh)
- **Phase 2 Extended Variables:**
  - $C_t$ = Battery charge (MWh)
  - $D_t$ = Battery discharge (MWh)
  - $SOC_t$ = Battery State of Charge (MWh)
  - $Unmet_t$ = Unmet Demand (MWh, optional)

All variables are **continuous** and **non-negative** (LP, not MIP). To preserve pure LP, there are no binary variables to prevent simultaneous charge/discharge (the solver naturally avoids it due to efficiency losses and costs).

### Objective Function (Minimize)

$$Z = \sum_{t=0}^{23} \left( C_s \cdot S_t + C_w \cdot W_t + C_{th} \cdot T_t + P_{unmet} \cdot Unmet_t \right)$$

Where $C_s, C_w, C_{th}$ are the costs per MWh. $P_{unmet}$ is a heavy penalty for unmet demand (e.g., 50,000 ₹/MWh).

### Constraints

| Constraint | Equation | Type |
|---|---|---|
| Demand Balance | $S_t + W_t + T_t + D_t - C_t + Unmet_t = Demand_t \quad \forall t$ | Equality |
| Solar Availability | $S_t \leq \text{SolarAvail}_t \quad \forall t$ | Upper bound |
| Wind Availability | $W_t \leq \text{WindAvail}_t \quad \forall t$ | Upper bound |
| Thermal Capacity | $T_t \leq \text{ThermalCap} \quad \forall t$ | Upper bound |
| Thermal Ramp | $\|T_t - T_{t-1}\| \leq \text{RampLimit}$ | Phase 2 |
| Hourly CO₂ Cap | $T_t \cdot \text{CO2}_{th} \leq \text{CO2Cap}_t$ | Phase 2 |
| Battery Dynamics | $SOC_t = SOC_{t-1} + \eta_c C_t - D_t / \eta_d$ | Phase 2 |
| Non-Negativity | All variables $\geq 0 \quad \forall t$ | Lower bound |

**Note on Shadow Prices:** The dual values (shadow prices) of the demand-balance constraints are extracted, representing the marginal cost of energy at each hour.

---

## 4. Features

### Core
- ✅ LP optimization using PuLP + CBC solver
- ✅ Pre-optimization feasibility check (per-hour capacity vs demand)
- ✅ Data validation (columns, types, ranges, duplicates, availability vs capacity)
- ✅ Post-solve constraint verification (demand balance, bounds, cost match, phase 2 checks)
- ✅ Inter-temporal constraints (Thermal Ramp limits, Battery State of Charge)

### Results & Analytics
- Optimal hourly dispatch table (Solar, Wind, Thermal, Battery, Unmet)
- Total minimum generation cost, Renewable share, Thermal dependency
- CO₂ emissions (kg) by source and total
- Source-wise cost breakdown
- Hourly Shadow Prices (Marginal Cost)
- Battery state of charge (SOC) dynamics

### Scenario Analysis (12 scenarios)
- **Phase 1 Scenarios**: Baseline, High Demand, Low Solar, High Thermal Cost, Increased Renewable
- **Phase 2 Scenarios**: Extended Baseline, Tight Evening CO₂ Cap, Tight CO₂ + Battery, Insufficient Battery, Tight Ramp, Relaxed Ramp, Battery Arbitrage Only

### UI (Streamlit)
- Dashboard with 4 core KPIs and 4 advanced Phase 2 metrics
- Input Configuration with Phase 2 data overrides
- Optimization page with Phase 2 feature toggles and mathematical formulation
- Results page with 7 interactive Plotly charts (including SOC and Shadow Prices)
- Scenario Analysis with Phase 1 vs Phase 2 comparative analysis

---

## 5. Technology Stack

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

## 6. Installation

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

## 7. How to Run

### Start the Application

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`.

### Recommended Demo Flow

1. **Dashboard** — View KPI summary (run optimization first)
2. **Optimization** → Toggle Phase 2 Advanced Options → Run LP
3. **Results** → View dispatch table, Battery SOC, and Shadow Prices
4. **Scenario Analysis** → Select Phase 2 scenarios → Run → Compare battery impact

### Run Tests

```bash
python -m pytest tests/ -v -W ignore::DeprecationWarning
```

### Run Standalone Verification

```bash
python verify_lp.py
```

---

## 8. Dataset Schema

*Original Phase 1 schema is preserved.*

### `data/co2_cap.csv` (Phase 2)
| Column | Type | Description |
|---|---|---|
| `hour` | int (0–23) | Hour of the day |
| `co2_cap_kg` | float ≥ 0 | Maximum allowable CO₂ emissions (kg) in that hour |

### `data/battery.csv` (Phase 2)
Contains key-value pairs for `capacity_mwh`, `charge_rate_max_mw`, `discharge_rate_max_mw`, `charge_efficiency`, `discharge_efficiency`, `initial_soc_mwh`, `min_soc_mwh`, `max_soc_mwh`.

---

## 9. Default Dataset Assumptions

This project uses a **synthetic demonstration dataset** inspired by typical South Asian grid characteristics.

### Phase 2 Configurations
- **Battery**: 400 MWh capacity, 100 MW charge/discharge rate, 90% efficiency.
- **Ramp Limit**: 200 MW/hr for Thermal generator.
- **CO₂ Cap**: Non-binding for most hours, but constrained to 550,000 kg during evening peak (hours 17-20) to demonstrate inter-temporal battery pre-positioning.

---

## 10. LP Model Results (Default Dataset)

Phase 2 results depend heavily on the advanced toggles selected. With all Phase 2 features (Battery + CO₂ Cap) enabled:
- The battery **charges** during midday (hours 10-14) using excess cheap renewable energy.
- The battery **discharges** during the evening peak (hours 17-20) when the CO₂ cap restricts thermal output.
- Inter-temporal optimization successfully avoids unmet demand.

---

## 11. Scenario Descriptions

| Scenario | Focus | Expected Effect |
|---|---|---|
| P2 Tight CO₂ (No Batt) | Strict emissions | Infeasible/unmet demand without storage |
| P2 Tight CO₂ + Battery | Inter-temporal | Optimal; battery shifts energy to meet cap |
| P2 Tight Ramp | Flexibility limit | Model pre-positions thermal output early |
| P2 Battery Only | Arbitrage | Battery smooths generation costs |

---

## 12. Project Structure

```
RenewOpt/
│
├── app.py                          # Streamlit entry point
│
├── data/
│   ├── demand.csv                  # 24-hour demand profile
│   ├── solar_availability.csv      
│   ├── wind_availability.csv       
│   ├── generators.csv              # Generator parameters
│   ├── co2_cap.csv                 # Hourly CO2 emission caps
│   └── battery.csv                 # Battery storage specifications
│
├── src/
│   ├── data_loader.py              # Load datasets + phase 2 configs
│   ├── validation.py               # Input validation layer
│   ├── optimizer.py                # Core LP formulation (Phase 1 + 2)
│   ├── calculations.py             # Derived metrics
│   └── scenarios.py                # Scenario definitions
│
├── components/
│   ├── dashboard.py                # Dashboard KPI page
│   ├── input_config.py             # Input configuration
│   ├── results.py                  # Results + charts page
│   └── scenario_analysis.py        # Scenario comparison page
│
├── tests/
│   ├── test_optimizer.py           # Base optimizer tests
│   ├── test_validation.py          # Data validation tests
│   ├── test_calculations.py        # Metrics tests
│   └── test_phase2.py              # 36 Advanced Phase 2 integration tests
│
├── verify_lp.py                    # Standalone mathematical verification
├── requirements.txt
├── README.md
└── .gitignore
```

---

## 13. Automated Tests

- `test_validation.py`: 11 tests
- `test_optimizer.py`: 8 tests
- `test_calculations.py`: 7 tests
- `test_phase2.py`: 36 tests

**Total: 62 tests**

**Verified result: 62/62 tests passing**

---

## 14. Limitations

- **No transmission**: Single-node model; no network constraints
- **Deterministic**: Renewable availability is fixed (no stochastic uncertainty)
- **Synthetic data**: Default dataset is not real-world grid measurements
- **No unit commitment**: On/off decisions not modeled (LP only, no integer variables)
- **No AC power flow**: Electrical engineering constraints not modeled

---

## 15. Future Scope

- Stochastic optimization for uncertain renewable availability
- Multi-objective optimization (cost vs. emissions trade-off with Pareto frontier)
- Transmission network constraints (DC power flow)
- Multi-node dispatch
- Machine learning demand forecasting
- Real-time data integration (e.g., POSOCO/NPP APIs)

---

## 16. References and Data Sources

- **PuLP Documentation**: https://coin-or.github.io/pulp/
- **CBC Solver**: https://github.com/coin-or/Cbc
- **Central Electricity Authority (CEA)**: https://cea.nic.in — used for contextual understanding of Indian grid characteristics
- **Ministry of New and Renewable Energy (MNRE)**: https://mnre.gov.in — renewable capacity context
- **National Power Portal (NPP)**: https://npp.gov.in — demand profile context

> **Data Attribution:** All numerical values in `data/` are **synthetic and project-generated**.
> They are inspired by publicly available Indian electricity grid characteristics but do not represent
> actual measurements. They are suitable for academic demonstration only.

---

## 17. Team Members

*[Add team member names here]*

---

## 18. Academic Course Alignment

- **Course Outcomes:** CO1 (Linear Programming), CO3 (OR in industrial optimization)
- **Technique:** Linear Programming
- **Solver:** PuLP + CBC
- **Viva-ready:** Mathematical model is fully transparent and displayed in the application UI

---

*RenewOpt — An Operations Research mini-project for optimal renewable energy dispatch.*
