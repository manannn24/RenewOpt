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

All variables are **continuous** and **non-negative** (LP, not MIP).

### Objective Function (Minimize)

$$Z = \sum_{t=0}^{23} \left( C_s \cdot S_t + C_w \cdot W_t + C_{th} \cdot T_t \right)$$

Where $C_s$, $C_w$, $C_{th}$ are the cost per MWh for each source.

### Constraints

| Constraint | Equation | Type |
|---|---|---|
| Demand Balance | $S_t + W_t + T_t = D_t \quad \forall t$ | Equality |
| Solar Availability | $S_t \leq \text{SolarAvail}_t \quad \forall t$ | Upper bound |
| Wind Availability | $W_t \leq \text{WindAvail}_t \quad \forall t$ | Upper bound |
| Thermal Capacity | $T_t \leq \text{ThermalCap} \quad \forall t$ | Upper bound |
| Non-Negativity | $S_t, W_t, T_t \geq 0 \quad \forall t$ | Lower bound |

**Model size:** 72 decision variables, 24 hourly demand-balance equality constraints, with variable bounds enforcing non-negativity, renewable availability, and thermal capacity.

---

## 4. Features

### Core
- ✅ LP optimization using PuLP + CBC solver
- ✅ Pre-optimization feasibility check (per-hour capacity vs demand)
- ✅ Data validation (columns, types, ranges, duplicates, availability vs capacity)
- ✅ Post-solve constraint verification (demand balance, bounds, cost match)

### Results & Analytics
- Optimal hourly dispatch table (Solar, Wind, Thermal)
- Total minimum generation cost
- Renewable share (%) = (Solar + Wind) / Total × 100
- Thermal dependency (%) = Thermal / Total × 100
- CO₂ emissions (kg) by source and total
- Source-wise cost breakdown

### Scenario Analysis (5 scenarios)
1. **Baseline** — Normal operating conditions
2. **High Demand** — Demand increased by 20% (may become infeasible)
3. **Low Solar** — Solar availability reduced to 50%
4. **High Thermal Cost** — Thermal cost increased by 30%
5. **Increased Renewable Capacity** — Solar capacity +200 MW

### UI (Streamlit)
- Dashboard with 4 KPI cards
- Input Configuration (default dataset or CSV upload + generator editor)
- Optimization page with full mathematical formulation displayed
- Results page with dispatch table and 5 interactive Plotly charts
- Scenario Analysis with comparison table and charts

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
2. **Optimization** → View LP formulation → Click "Run LP Optimization"
3. **Results** → View dispatch table and all charts
4. **Scenario Analysis** → Select scenarios → Run → Compare

### Run Tests

```bash
python -m pytest tests/ -v
```

### Run Standalone Verification

```bash
python verify_lp.py
```

---

## 8. Dataset Schema

### `data/demand.csv`

| Column | Type | Description |
|---|---|---|
| `hour` | int (0–23) | Hour of the day |
| `demand_mw` | float ≥ 0 | Electricity demand (MWh for 1-hour interval) |

### `data/solar_availability.csv`

| Column | Type | Description |
|---|---|---|
| `hour` | int (0–23) | Hour of the day |
| `solar_available_mw` | float ≥ 0 | Available solar generation (≤ installed capacity) |

### `data/wind_availability.csv`

| Column | Type | Description |
|---|---|---|
| `hour` | int (0–23) | Hour of the day |
| `wind_available_mw` | float ≥ 0 | Available wind generation (≤ installed capacity) |

### `data/generators.csv`

| Column | Type | Description |
|---|---|---|
| `source` | str | Generator name (`Solar`, `Wind`, `Thermal`) |
| `max_capacity_mw` | float > 0 | Installed capacity (MW) |
| `cost_per_mwh` | float ≥ 0 | Generation cost (₹/MWh) |
| `co2_per_mwh` | float ≥ 0 | CO₂ emission factor (kg/MWh) |

---

## 9. Default Dataset Assumptions

This project uses a **synthetic demonstration dataset** inspired by typical South Asian grid characteristics.
It does **not** represent actual measured grid data.

### Generator Parameters

| Source | Capacity (MW) | Cost (₹/MWh) | CO₂ (kg/MWh) |
|---|---|---|---|
| Solar | 400 | 10.00 | 0 |
| Wind | 300 | 15.00 | 0 |
| Thermal | 800 | 85.00 | 820 |

**Cost rationale:** Solar and Wind marginal costs are near-zero (no fuel cost). Thermal represents
coal/gas-based generation. The ₹ symbol is used for illustration; units are consistent internally.

**CO₂ rationale:** Solar and Wind have zero direct emissions. 820 kg/MWh for Thermal is representative
of a mixed coal/gas fleet.

### Demand Profile

- Night hours (0–5): 545–620 MW (low residential/industrial load)
- Morning ramp (6–9): 700–850 MW
- Midday (10–15): 810–840 MW
- Evening peak (16–20): 870–950 MW (highest at hour 19: 950 MW)
- Late evening (21–23): 700–850 MW

### Solar Profile

- Night (0–5, 19–23): 0 MW
- Peak at hour 12: 400 MW
- Bell-shaped curve across hours 6–18

### Wind Profile

- Variable between 110–195 MW throughout the day
- Higher at night and early morning

---

## 10. LP Model Results (Default Dataset)

```
Status:             Optimal
Total Cost:         ₹1,073,825
Total Demand:       18,505 MWh
Total Generation:   18,505 MWh
Renewable Share:    37.34%
Thermal Dependency: 62.66%
CO₂ Emissions:      9,507,900 kg
```

**Key LP observations:**
- The optimizer always dispatches full available solar (cheapest at ₹10/MWh) when possible
- Wind is dispatched fully at all hours (₹15/MWh < ₹85/MWh thermal)
- Thermal fills the residual demand at all hours
- Evening peak (hours 17–20) requires maximum thermal contribution

---

## 11. Scenario Descriptions

| Scenario | Modification | Expected Effect |
|---|---|---|
| Baseline | None | Reference solution |
| High Demand (+20%) | Demand × 1.20 | May become infeasible; higher thermal use |
| Low Solar (−50%) | Solar availability × 0.50 | More thermal, higher cost and CO₂ |
| High Thermal Cost (+30%) | Thermal cost × 1.30 | Dispatch unchanged (no cheaper alternative), higher total cost |
| Increased Renewable (+200 MW Solar) | Solar capacity 400→600 MW | More solar, lower cost and CO₂ |

**Note on Increased Renewable Capacity:** This scenario assumes that the newly added solar capacity
has the same normalized hourly generation profile as the existing capacity (scaled proportionally).

**Note:** High Demand (20% increase) becomes **infeasible** with the default dataset because
demand at peak hours (e.g., 950 × 1.20 = 1,140 MW) exceeds available capacity
(0 solar + 180 wind + 800 thermal = 980 MW). This is correctly detected and reported.

---

## 12. Project Structure

```
RenewOpt/
│
├── app.py                          # Streamlit entry point
│
├── data/
│   ├── demand.csv                  # 24-hour demand profile
│   ├── solar_availability.csv      # Hourly solar availability
│   ├── wind_availability.csv       # Hourly wind availability
│   └── generators.csv              # Generator parameters
│
├── src/
│   ├── __init__.py
│   ├── data_loader.py              # Load default or uploaded CSVs
│   ├── validation.py               # Input validation layer
│   ├── optimizer.py                # LP formulation and PuLP solver
│   ├── calculations.py             # Derived metrics (cost, renewable%, CO₂)
│   └── scenarios.py                # Scenario engine (5 scenarios)
│
├── components/
│   ├── __init__.py
│   ├── dashboard.py                # Dashboard KPI page
│   ├── input_config.py             # Input configuration page
│   ├── results.py                  # Results + charts page
│   └── scenario_analysis.py       # Scenario comparison page
│
├── tests/
│   ├── test_optimizer.py           # 9 optimizer tests (LP correctness)
│   ├── test_validation.py          # 6 validation tests
│   └── test_calculations.py       # 7 metrics/calculations tests
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

**Total: 26 tests**

**Verified result: 26/26 tests passing**

---

## 14. Limitations

- **No storage**: Battery storage is not modeled (future extension)
- **No transmission**: Single-node model; no network constraints
- **Deterministic**: Renewable availability is fixed (no stochastic uncertainty)
- **No ramp constraints**: Thermal dispatch can change freely between hours
- **Synthetic data**: Default dataset is not real-world grid measurements
- **No unit commitment**: On/off decisions not modeled (LP only, no integer variables)
- **No AC power flow**: Electrical engineering constraints not modeled

---

## 15. Future Scope

- Stochastic optimization for uncertain renewable availability
- Battery energy storage (charging/discharging variables + state-of-charge constraints)
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
