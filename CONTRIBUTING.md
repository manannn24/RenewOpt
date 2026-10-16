# Contributing to RenewOpt

**RenewOpt** is an academic Operations Research platform for renewable energy economic dispatch optimization developed as an undergraduate academic group project by **Manan Jain**, **Behlah Kathavala**, and **Devansh Mehta**.

---

## Project Status & Contribution Policy

- **Academic Scope & Team-Only Contributions:** RenewOpt is maintained as an academic project by its core student team. **The project is not currently accepting external contributions or unsolicited pull requests.**
- **Open Source Licensing:** RenewOpt is open-source software under the terms of the [MIT License](LICENSE). Public repository visibility permits anyone to fork, clone, inspect, and reuse the codebase in compliance with the license; however, public visibility does not grant repository write access.
- **Canonical Repository Governance:** Only the authorized project team may approve and merge changes into the canonical repository, subject to GitHub repository permissions and branch protection rules.

---

## Code of Conduct

We are committed to providing a welcoming, collaborative, and professional environment. Please maintain academic and engineering integrity at all times.

---

## Development Setup

### 1. Prerequisites
- Python 3.8 to 3.13
- Git

### 2. Clone the Repository
```bash
git clone https://github.com/manannn24/RenewOpt.git
cd RenewOpt
```

### 3. Virtual Environment
```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Running the Application

Launch the interactive Streamlit web interface:
```bash
streamlit run app.py
```

---

## Testing & Mathematical Verification

RenewOpt enforces rigorous automated testing and independent mathematical verification:

1. **Run Pytest Suite**:
   ```bash
   pytest tests/ -v -W ignore::DeprecationWarning
   ```
   All 77 tests must pass without errors.

2. **Run Standalone LP Verification**:
   ```bash
   python verify_lp.py
   ```
   This script verifies that the CBC solver solution satisfies all physical, temporal, and economic constraints within strict tolerances ($< 10^{-3}$ MW demand balance, zero ramp violations).

---

## Development Guidelines

1. **Preserve Mathematical Integrity**: All core optimization logic must preserve the documented Linear Programming (LP) formulation. Changes affecting the mathematical model must not be introduced unless an explicitly reviewed project requirement calls for a change.
2. **Deterministic & Continuous**: Formulations in `src/optimizer.py` must remain continuous and linear (LP). If integer/binary variables are introduced in future work (e.g., discrete unit commitment), they must be clearly isolated and documented as MILP extensions.
3. **Documentation & Traceability**: When modifying generator parameters, dataset structures, or constraints, corresponding documentation in `README.md`, validation routines in `src/validation.py`, and test cases in `tests/` must be updated accordingly.
4. **No Secrets or Local Deliverables**: Do not commit API credentials, personal machine paths, private academic grading deliverables, or internal working notes.

---

## Contribution & Branching Workflow

For the authorized project team members, all development follows this structured workflow:

1. **Do Not Push Directly to `main`**: All modifications must be proposed via pull requests. Direct commits or pushes to the `main` branch are restricted.
2. **Create a Dedicated Feature Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Commit & Push**:
   Keep commit messages clear, descriptive, and focused:
   ```bash
   git commit -m "feat: add multi-fuel thermal ramp test"
   git push origin feature/your-feature-name
   ```
4. **Open a Pull Request**:
   - Open a pull request targeting the `main` branch.
   - Describe the changes, motivation, and test results.
   - Verify that automated CI checks, `pytest tests/`, and `python verify_lp.py` pass.
   - Any modification affecting the LP formulation, physical constraints, dataset assumptions, or verification behavior requires rigorous peer review, full documentation updates, and corresponding test coverage.
5. **Code Review, Ownership & Merge Policy**:
   - **Primary Maintainer:** Manan Jain ([@manannn24](https://github.com/manannn24)) serves as the primary maintainer and project lead for RenewOpt.
   - **Shared Code Ownership & Deadlock Prevention:** Under GitHub branch protection rules, pull request authors cannot approve their own pull requests. To prevent approval deadlocks while enforcing genuine peer review, all three project team members (**Manan Jain**, **Behlah Kathavala**, and **Devansh Mehta**) are designated as code owners in `.github/CODEOWNERS`.
   - **Independent Peer Review:** Every pull request targeting `main` must receive at least one independent review and approval from an eligible team code owner other than the author before merging.
   - **Verification Gate:** No pull request may be merged unless automated CI checks, test suites, and mathematical verifications pass completely.
   - *Note on GitHub Plan Support & Governance:* These approval requirements and merge restrictions depend on branch protection rules or repository rulesets configured in GitHub repository settings. GitHub Free provides full support for protected branches and CODEOWNERS enforcement on public repositories; on private repositories, support for certain enforcement rules depends on the account's GitHub plan. (Adding `.github/CODEOWNERS` defines file ownership mapping, but actual enforcement must be enabled in GitHub repository settings).
