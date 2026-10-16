# RenewOpt: Renewable Energy Grid Dispatch Optimization

[![CI](https://github.com/manannn24/RenewOpt/actions/workflows/ci.yml/badge.svg)](https://github.com/manannn24/RenewOpt/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Optimization: PuLP](https://img.shields.io/badge/Optimization-PuLP%20%2F%20CBC-green.svg)](https://coin-or.github.io/pulp/)

An open-source Operations Research (OR) platform that solves the **Economic Dispatch Problem** for electrical grids with high penetrations of variable renewable energy (Solar and Wind), thermal generation, and battery energy storage. Formulated as a Linear Program (LP) in Python using **PuLP** and the **COIN-OR CBC** solver, RenewOpt supports both rapid 24-hour classroom demonstrations and large-scale **Full-Year (8,760-hour)** planning horizons.

---

## Project Team

This project was developed as an academic Operations Research group project by:

- **Manan Jain** — [@manannn24](https://github.com/manannn24)
- **Behlah Kathavala** — [@behlah-rgb](https://github.com/behlah-rgb)
- **Devansh Mehta** — [@dmsd723](https://github.com/dmsd723)

---

## Table of Contents

- [Project Team](#project-team)
1. [Operations Research Context & Motivation](#1-operations-research-context--motivation)
2. [Mathematical Formulation](#2-mathematical-formulation)
3. [Phase 1 vs. Phase 2 Features](#3-phase-1-vs-phase-2-features)
4. [Architecture & Repository Layout](#4-architecture--repository-layout)
5. [Prerequisites & Installation](#5-prerequisites--installation)
6. [How to Run](#6-how-to-run)
7. [Datasets & Provenance](#7-datasets--provenance)
8. [Automated Testing & Mathematical Verification](#8-automated-testing--mathematical-verification)
9. [Infeasibility Diagnostics & Reliability Mode](#9-infeasibility-diagnostics--reliability-mode)
10. [Known Limitations & OR Trade-offs](#10-known-limitations--or-trade-offs)
11. [Troubleshooting](#11-troubleshooting)
12. [Contributing & License](#12-contributing--license)

---

## 1. Operations Research Context & Motivation

Modern electricity grids face a core operational challenge: supply must continuously match demand at every second, while variable renewable energy (VRE) generation fluctuates with weather conditions. Grid operators require formal mathematical models to determine the optimal dispatch schedules that minimize economic generation costs while strictly adhering to physical generator limits, environmental regulations, and energy storage conservation laws.

**RenewOpt** models this system as a deterministic **Linear Program (LP)**:
- **Primary Objective:** Minimize total grid generation and operating costs over the configured planning horizon.
- **Analytical Property:** Because solar and wind have lower marginal costs (₹10/MWh and ₹15/MWh) than thermal units (₹85/MWh), the optimizer naturally prioritizes renewable generation to the maximum extent permitted by availability and system constraints.

---

## 2. Mathematical Formulation

The dispatch problem is solved across discrete time periods $t \in \mathcal{T} = \{0, 1, \dots, N-1\}$, where $N = 24$ for single-day studies or $N = 8,760$ for full-year hourly planning horizons.

### 2.1 Sets, Parameters, and Decision Variables

| Category | Notation | Units | Description |
|---|---|---|---|
| **Index** | $t \in \mathcal{T}$ | hours | Time period index ($0 \le t < N$) |
| **Parameters** | $D_t$ | MW / MWh | Electricity demand at hour $t$ |
| | $\text{SolarAvail}_t$ | MW | Maximum available solar power at hour $t$ |
| | $\text{WindAvail}_t$ | MW | Maximum available wind power at hour $t$ |
| | $T_{max}$ | MW | Maximum thermal generator capacity (800 MW) |
| | $c_s, c_w, c_{th}$ | ₹/MWh | Marginal generation cost ($c_s=10, c_w=15, c_{th}=85$) |
| | $c_{pen}$ | ₹/MWh | Reliability penalty for unmet demand (₹50,000/MWh) |
| | $\Delta T_{max}$ | MW/h | Thermal ramp rate limit |
| | $T_{init}$ | MW | Initial thermal output at hour 0 |
| | $e_{th}$ | kg/MWh | Thermal emission factor (820 kg CO₂/MWh) |
| | $\text{CO2Cap}_t$ | kg | Hourly environmental emission cap at hour $t$ |
| | $B_{cap}$ | MWh | Battery storage nameplate capacity (400 MWh) |
| | $C_{max}, D_{max}$ | MW | Maximum charging and discharging rates (100 MW) |
| | $\text{SOC}_{min}, \text{SOC}_{max}$ | MWh | State-of-charge lower and upper bounds |
| | $\text{SOC}_{init}$ | MWh | Initial battery state-of-charge |
| | $\eta_c, \eta_d$ | - | Charging and discharging efficiencies ($\eta_c=\eta_d=0.948$) |
| **Variables** | $S_t \ge 0$ | MWh | Solar energy dispatched at hour $t$ |
| | $W_t \ge 0$ | MWh | Wind energy dispatched at hour $t$ |
| | $T_t \ge 0$ | MWh | Thermal energy dispatched at hour $t$ |
| | $C_t \ge 0$ | MWh | Battery energy charged at hour $t$ |
| | $D_t \ge 0$ | MWh | Battery energy discharged at hour $t$ |
| | $\text{SOC}_t \ge 0$ | MWh | Energy stored in battery at end of hour $t$ |
| | $Unmet_t \ge 0$ | MWh | Unmet demand slack variable (Reliability mode) |

### 2.2 Objective Function

Minimize the total generation cost plus penalties for any unmet demand:

$$\min Z = \sum_{t \in \mathcal{T}} \left( c_s S_t + c_w W_t + c_{th} T_t + c_{pen} Unmet_t \right)$$

*Note: Battery storage incurs no direct marginal cost in the objective function; cycling costs are represented implicitly through round-trip efficiency losses ($\eta_c \cdot \eta_d < 1.0$).*

### 2.3 Constraints

1. **Demand Balance (Hourly Grid Equilibrium):**
   $$S_t + W_t + T_t + D_t - C_t + Unmet_t = D_t \quad \forall t \in \mathcal{T}$$

2. **Renewable and Thermal Capacity Bounds:**
   $$0 \le S_t \le \text{SolarAvail}_t \quad \forall t \in \mathcal{T}$$
   $$0 \le W_t \le \text{WindAvail}_t \quad \forall t \in \mathcal{T}$$
   $$0 \le T_t \le T_{max} \quad \forall t \in \mathcal{T}$$

3. **Thermal Ramping Physics (Inter-temporal Rate-of-Change):**
   $$|T_t - T_{t-1}| \le \Delta T_{max} \quad \forall t > 0$$
   $$|T_0 - T_{init}| \le \Delta T_{max} \quad (t = 0)$$
   *Linearized as two complementary inequalities:*
   $$T_t - T_{t-1} \le \Delta T_{max}, \quad T_{t-1} - T_t \le \Delta T_{max}$$

4. **Hourly Environmental CO₂ Emission Caps:**
   $$T_t \cdot e_{th} \le \text{CO2Cap}_t \quad \forall t \in \mathcal{T}$$

5. **Battery State of Charge (SOC) Conservation:**
   $$\text{SOC}_t = \text{SOC}_{t-1} + \eta_c C_t - \frac{D_t}{\eta_d} \quad \forall t > 0$$
   $$\text{SOC}_0 = \text{SOC}_{init} + \eta_c C_0 - \frac{D_0}{\eta_d} \quad (t = 0)$$
   $$\text{SOC}_{min} \le \text{SOC}_t \le \text{SOC}_{max} \quad \forall t \in \mathcal{T}$$
   $$0 \le C_t \le C_{max}, \quad 0 \le D_t \le D_{max} \quad \forall t \in \mathcal{T}$$

6. **Dual Values (Shadow Prices):**
   Dual multipliers $\lambda_t = \frac{\partial Z^*}{\partial D_t}$ are extracted directly from the demand balance equality constraints, representing the marginal system cost (₹/MWh) to supply one additional unit of load at hour $t$.

---

## 3. Phase 1 vs. Phase 2 Features

| Feature | Phase 1 (Baseline) | Phase 2 (Advanced RenewOpt) |
|---|---|---|
| **Planning Horizon** | 24 hours | 24 hours and 8,760 hours (Full Year) |
| **Problem Type** | Static dispatch (independent hours) | Inter-temporally coupled dynamic LP |
| **Decision Variables** | 72 variables ($S_t, W_t, T_t$) | Up to 61,320 variables ($S_t, W_t, T_t, C_t, D_t, \text{SOC}_t, Unmet_t$) |
| **Constraints** | 24 balance + capacity bounds | ~35,040 constraints (Balance, Bounds, SOC, Ramp, CO₂) |
| **Energy Storage** | Not modeled | Bidirectional battery with charge/discharge efficiencies |
| **Generator Dynamics** | Unconstrained hourly jumps | Explicit thermal ramp limits ($\Delta T \le \text{RampLimit}$) |
| **Policy Constraints** | None | Hourly CO₂ emissions cap |
| **Infeasibility Handling**| Solver reports infeasible | Reliability Mode (penalized slack) + Diagnostic Analyzer |
| **Duality Analysis** | Basic cost calculation | Hourly marginal shadow price extraction ($\lambda_t$) |
| **Analytics** | Daily summary cards | Daily + Full-Year Monthly Aggregation & Reconciliation |

---

## 4. Architecture & Repository Layout

```text
RenewOpt/
├── app.py                          # Streamlit application entry point & page router
├── verify_lp.py                    # Independent mathematical LP verification script
├── requirements.txt                # Pinned production & development dependencies
├── LICENSE                         # MIT open-source license
├── CONTRIBUTING.md                 # Contributor guidelines and workflow
├── README.md                       # Comprehensive project documentation
├── .gitignore                      # Git ignore rules for caches, envs, and local docs
│
├── data/                           # 24-Hour Demonstration Dataset
│   ├── demand.csv                  # 24-hour load profile (545 - 950 MW)
│   ├── solar_availability.csv      # Diurnal solar availability (0 - 400 MW)
│   ├── wind_availability.csv       # Variable wind availability (110 - 195 MW)
│   ├── generators.csv              # Generator capacities, costs, and emissions
│   ├── battery.csv                 # Battery storage specifications & efficiencies
│   └── co2_cap.csv                 # Hourly emission caps (550k kg peak / 1M kg off-peak)
│
├── data_8760/                      # 8,760-Hour Full-Year Dataset
│   ├── demand.csv                  # Chronological 8,760-hour demand (timestamp, hour_of_day, demand_mw)
│   ├── solar_availability.csv      # Full-year seasonal solar generation profile
│   ├── wind_availability.csv       # Full-year seasonal wind generation profile
│   └── generators.csv              # Full-year generator specifications
│
├── src/                            # Core Operations Research & Pipeline Modules
│   ├── __init__.py                 # Python package identifier
│   ├── optimizer.py                # Primary PuLP LP formulation, CBC solver interface & dual extraction
│   ├── diagnostic.py               # Infeasibility diagnostic analyzer & constraint relaxation
│   ├── data_loader.py              # Data ingestion, chronological indexing (0..8759), bundle builder
│   ├── validation.py               # Schema integrity, bounds checking, and pre-solve feasibility
│   ├── calculations.py             # Metrics derivation (renewable share, emissions, monthly reconciliation)
│   └── scenarios.py                # Pre-configured scenario analysis definitions
│
├── components/                     # Streamlit User Interface Components
│   ├── __init__.py                 # UI package identifier
│   ├── dashboard.py                # Executive KPI cards & monthly summary view
│   ├── input_config.py             # Dataset selection, data explorer & generator editor
│   ├── results.py                  # Optimal dispatch tables, Plotly area charts & shadow price graphs
│   └── scenario_analysis.py        # Multi-scenario comparisons & comparative bar charts
│
├── tests/                          # Automated Pytest Suite (77 Tests)
│   ├── __init__.py                 # Test package identifier
│   ├── test_optimizer.py           # 8 tests: Basic LP optimality, non-negativity, bounds
│   ├── test_validation.py          # 11 tests: Schema validation, hour ranges, missing values
│   ├── test_calculations.py        # 7 tests: Cost sums, renewable percentage, emission totals
│   ├── test_phase2.py              # 36 tests: Battery SOC dynamics, ramp limits, shadow prices, reliability
│   ├── test_ramp_boundaries.py     # 5 tests: Exact mathematical ramp boundary and non-cyclic checks
│   ├── test_8760.py                # 5 tests: 8,760-hour data integrity and monthly aggregation
│   └── test_co2_interaction.py     # 5 tests: 24h CO₂ cap loading, binding states, battery shifting
│
└── .github/                        # GitHub Configuration
    ├── workflows/ci.yml            # Automated CI testing on Python 3.10, 3.11, 3.12
    └── ISSUE_TEMPLATE/bug_report.md# Standardized bug reporting template
```

---

## 5. Prerequisites & Installation

### 5.1 System Prerequisites
- **Python**: Version 3.8, 3.9, 3.10, 3.11, 3.12, or 3.13.
- **Operating System**: Windows, macOS, or Linux.
- **Solver**: COIN-OR CBC is pre-bundled automatically by the `pulp` Python package. No external solver installation is required.

### 5.2 Step-by-Step Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/manannn24/RenewOpt.git
   cd RenewOpt
   ```

2. **Create and activate a virtual environment:**
   - **Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
   - **Windows (Command Prompt):**
     ```cmd
     python -m venv .venv
     .venv\Scripts\activate.bat
     ```
   - **macOS / Linux (bash/zsh):**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install required dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 6. How to Run

### 6.1 Launch the Interactive Web Application

```bash
streamlit run app.py
```
Streamlit will launch locally at `http://localhost:8501`.

### 6.2 Recommended Walkthrough

1. **⚙️ Input Configuration:**
   - Select **Default Dataset (24 hours)** for interactive constraint exploration, or **Full Year Dataset (8760 hours)** for annual grid simulations.
   - Use the **Data Explorer** to view hourly trends across single days, date ranges, or full months.
2. **🔬 LP Optimization:**
   - Review the mathematical LP formulation rendered in LaTeX.
   - Configure Phase 2 toggles:
     - **Thermal Ramp Constraints:** Enable to force ramp-limited thermal transitions.
     - **Hourly CO₂ Cap:** Enforces emission caps (demonstrates pre-peak battery charging).
     - **Battery Storage:** Activates inter-temporal energy storage.
     - **Reliability Mode:** Prevents solver infeasibility by introducing penalized unmet demand slack.
   - Click **Run LP Optimization**.
3. **📈 Results:**
   - Inspect the hourly dispatch table with generation, battery charge/discharge, SOC, and shadow prices.
   - Review stacked area charts for supply vs. demand balance.
   - Inspect the hourly Shadow Price curve showing electricity marginal costs.
   - In full-year mode, inspect the **Monthly Aggregation** summary reconciling demand and fuel mix.
4. **🔄 Scenario Analysis:**
   - Select multiple operating scenarios (Baseline, High Demand, Low Solar, Tight Ramp, Tight CO₂ + Battery).
   - Click **Run Selected Scenarios** to inspect comparative cost, renewable share, and emission tables.

---

## 7. Datasets & Provenance

All datasets provided in `data/` and `data_8760/` are **synthetic and project-generated** for academic research and benchmarking. They are designed to reflect realistic operational profiles while remaining fully reproducible.

### 7.1 24-Hour Demonstration Dataset (`data/`)
- **Demand (`demand.csv`):** Realistic diurnal double-peak curve (early morning dip of 545 MW, morning rise to 850 MW, evening peak of 950 MW at hour 19). Total demand: 18,505 MWh.
- **Solar (`solar_availability.csv`):** Standard bell-curve availability peaking at 400 MW at hour 12, zero at night.
- **Wind (`wind_availability.csv`):** Moderately persistent night-and-evening profile ranging between 110 MW and 195 MW.
- **Generators (`generators.csv`):**
  - Solar: 400 MW capacity, ₹10/MWh, 0 kg CO₂/MWh
  - Wind: 300 MW capacity, ₹15/MWh, 0 kg CO₂/MWh
  - Thermal: 800 MW capacity, ₹85/MWh, 820 kg CO₂/MWh, 200 MW/h default ramp limit
- **Battery (`battery.csv`):** 400 MWh capacity, 100 MW charge/discharge rate, 0 MWh initial/min SOC, 400 MWh max SOC, $\eta_c = \eta_d = 0.948$ (round-trip efficiency $\approx 89.9\%$).
- **CO₂ Cap (`co2_cap.csv`):** Synthetic policy cap; 1,000,000 kg for unconstrained hours, tightened to **550,000 kg** during evening peak hours (17, 18, 19, 20).

### 7.2 Full-Year 8,760-Hour Dataset (`data_8760/`)
- Contains 8,760 hourly sequential records spanning a full calendar year (8,760 rows).
- Schema: `timestamp, hour_of_day, <metric>_mw`.
- Total Annual Demand: **31,032,896 MWh** across 365 days.
- Features distinct seasonal variations (summer solar peaks, monsoon/winter wind shifts).

---

## 8. Automated Testing & Mathematical Verification

RenewOpt enforces quality through two independent testing tiers:

### 8.1 Automated Pytest Suite (77 Tests)

Run the full test suite with warnings silenced:
```bash
pytest tests/ -v -W ignore::DeprecationWarning
```

**Test Coverage Breakdown:**
- `tests/test_optimizer.py` (8 tests): Small-scale known LP optimality, merit-order solar dispatch, zero-availability limits, demand balance, and infeasible input handling.
- `tests/test_validation.py` (11 tests): Schema checks, non-negativity enforcement, duplicate hours, missing columns, and pre-solve capacity sufficiency.
- `tests/test_calculations.py` (7 tests): Mathematical correctness of derived costs, renewable generation share, thermal dependency, and emissions calculations.
- `tests/test_phase2.py` (36 tests): Thermal ramping constraints, initial thermal output conditions, hourly CO₂ cap binding, battery charge/discharge bounds, SOC inter-temporal conservation, shadow price finiteness, and reliability mode penalties.
- `tests/test_ramp_boundaries.py` (5 tests): Precise boundary verification testing feasibility at exact ramp limits, infeasibility at $\text{limit} + \epsilon$, and non-cyclic year-end decoupling.
- `tests/test_8760.py` (5 tests): Full-year data validation, timestamp continuity, chronological indexing, and monthly aggregation reconciliation.
- `tests/test_co2_interaction.py` (5 tests): 24h CO₂ cap loading, exact 0..23 hour coverage, binding behavior, strict infeasibility, and emergent battery pre-charging behavior.

**Current Test Status:** **77 passed** (100% pass rate).

### 8.2 Standalone Mathematical Verification (`verify_lp.py`)

Run the standalone verification script:
```bash
python verify_lp.py
```

This script solves the optimization problem across baseline, Phase 2, and 8,760-hour configurations, and then independently verifies:
- Demand balance residual error across every hour: $\max |S_t + W_t + T_t + D_t - C_t + Unmet_t - D_t| < 10^{-3}$ MW (measured: $< 5 \times 10^{-5}$ MW).
- Generator dispatch respects bounds: $0 \le S_t \le \text{Avail}_t$, $0 \le W_t \le \text{Avail}_t$, $0 \le T_t \le 800$.
- Thermal ramp rate violations: strictly 0 violations across all 8,759 consecutive hour transitions.
- Objective function consistency: verifies that $\sum (\text{hourly costs}) = Z^*$ within float tolerance.

---

## 9. Infeasibility Diagnostics & Reliability Mode

In linear programming, combining physical ramp limits with inflexible demand can easily produce an **empty feasible region** (infeasibility):
- **Why Infeasibility Occurs:** In the 8,760-hour dataset, evening net load ramps up by as much as 1,400 MW/h when solar drops to zero. If the thermal ramp rate is restricted to a tight value (e.g. 200 MW/h) and battery storage is insufficient, no combination of generation can physically meet the hourly demand jump without violating ramp constraints.
- **Diagnostic Analyzer (`src/diagnostic.py`):** When a strict LP returns `Infeasible`, RenewOpt automatically runs an auxiliary relaxation to locate the exact bottleneck hour, reporting:
  - Critical hour of failure
  - Required generation jump vs. allowed ramp limit
  - Unmet power shortage
- **Reliability Mode (Penalized Slack):** By enabling Reliability Mode, the demand balance equation is relaxed using non-negative slack variables $Unmet_t \ge 0$, penalized at $c_{pen} = ₹50,000/\text{MWh}$ in the objective. This guarantees mathematical feasibility while clearly reporting the location and magnitude of necessary demand curtailment.

---

## 10. Known Limitations & OR Trade-offs

1. **Single-Node Grid (Copper-Plate Assumption):** The model assumes an unconstrained transmission network connecting all generators and loads. Locational Marginal Pricing (LMP) and transmission line thermal limits (DC/AC power flow) are not modeled.
2. **Deterministic Formulation:** Renewable availability and demand are assumed to be known with certainty. Stochastic programming and chance-constrained reserves are left for future research.
3. **Pure Linear Program (No Unit Commitment):** The model uses continuous variables only. Binary decisions—such as generator start-up/shutdown, minimum up/down run times, and non-linear heat-rate curves—require Mixed-Integer Linear Programming (MILP).
4. **Simultaneous Battery Charging & Discharging:**
   - *Theoretical Limitation:* In pure continuous LP, binary complementary exclusion flags ($z_t \in \{0, 1\}$ enforcing $C_t \cdot D_t = 0$) are omitted to preserve polynomial solvability and allow dual shadow price extraction.
   - *Physical Mitigation:* Because round-trip efficiency is strictly less than 1 ($\eta_c \cdot \eta_d = 0.948^2 \approx 0.899$), the cost-minimizing objective naturally disincentivizes simultaneous charging and discharging when thermal generation has positive marginal cost, as doing so destroys energy and increases cost. In rare hours with zero marginal cost or degenerate bases, minor simultaneous flows may theoretically occur.
5. **Shadow Prices vs. Real Market LMPs:** Shadow prices ($\lambda_t$) extracted from the LP reflect the marginal cost of the dual constraint in this single-node model. They do not include uplift payments, reserve margins, or transmission congestion components present in deregulated wholesale electricity markets.

---

## 11. Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'pulp'` | Virtual environment not active or dependencies uninstalled | Run `.venv\Scripts\activate` (or `source .venv/bin/activate`) and `pip install -r requirements.txt`. |
| `pulp.constants.PulpSolverError: Cannot find CBC` | Custom Python environment with incomplete binary wheels | PuLP includes CBC automatically for standard x86_64 architectures. If using an exotic platform, install CBC via package manager (`sudo apt-get install coinor-cbc` or `brew install cbc`). |
| `DeprecationWarning: Constructing LpVariable directly...` | PuLP 2.8+ deprecation notice for legacy variable construction | Benign PuLP internal warning; does not affect optimization. Suppressed automatically in tests via `-W ignore::DeprecationWarning`. |
| Port 8501 already in use | Previous Streamlit instance still running in background | Launch on an alternative port: `streamlit run app.py --server.port 8502`. |
| Infeasible result on strict 8,760h run | Net-load ramp rate exceeds thermal ramp limit | Enable **Reliability Mode** in Advanced Configuration, or relax the thermal ramp limit to $\ge 1,000$ MW/h. |

---

## 12. Contributing & License

### Contributing
Contributions to RenewOpt are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on coding standards, testing, and pull request procedures.

### License
This project is open-source software licensed under the **MIT License**. See the [LICENSE](LICENSE) file for the full license text.

### Attribution
- **Project Team:** Manan Jain, Behlah Kathavala, Devansh Mehta
- **Academic Context:** Academic Operations Research Group Project / Renewable Energy Economic Dispatch Optimization
- **Optimization Engines:** [PuLP](https://coin-or.github.io/pulp/) and [COIN-OR CBC](https://github.com/coin-or/Cbc)
