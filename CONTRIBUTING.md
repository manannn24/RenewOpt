# Contributing to RenewOpt

Thank you for your interest in contributing to **RenewOpt**, an open-source Operations Research platform for renewable energy economic dispatch optimization developed as an undergraduate academic group project.

---

## Code of Conduct

We are committed to providing a welcoming, collaborative, and professional environment. Please treat all contributors with respect and maintain academic and engineering integrity.

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
4. **No Secrets or Local Deliverables**: Do not commit API credentials, personal machine paths, private academic grading deliverables, or generated artifacts.

---

## Contribution & Branching Workflow

To maintain repository stability and academic provenance, all team members and contributors follow this workflow:

1. **Do Not Push Directly to `main`**: All modifications must be proposed via pull requests. Direct commits or pushes to the `main` branch are discouraged.
2. **Create a Dedicated Feature Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Commit & Push**:
   Keep commit messages clear, descriptive, and focused:
   ```bash
   git commit -m "feat: Add multi-fuel thermal ramp test"
   git push origin feature/your-feature-name
   ```
4. **Open a Pull Request**:
   - Open a pull request targeting the `main` branch.
   - Describe the changes, motivation, and test results.
   - Verify that automated CI checks, `pytest tests/`, and `python verify_lp.py` pass.
5. **Code Review, Ownership & Merge Policy**:
   - **Primary Maintainer:** Manan Jain ([@manannn24](https://github.com/manannn24)) serves as the primary maintainer and project lead for RenewOpt.
   - **Shared Code Ownership & Deadlock Prevention:** Under GitHub branch protection rules, pull request authors cannot approve their own pull requests. If only a single individual were configured as the code owner, any pull request authored by the primary maintainer would encounter an approval deadlock. To eliminate this deadlock while preserving peer review, all three project team members (**Manan Jain**, **Behlah Kathavala**, and **Devansh Mehta**) are designated as code owners in `.github/CODEOWNERS`.
   - **Independent Peer Review:** Every pull request targeting `main` must receive at least one independent review and approval from an eligible team code owner other than the author before merging. For contributions submitted by collaborators, review and approval by the primary maintainer (or an eligible co-owner) are required.
   - *Note on GitHub Plan Support & Governance:* These approval requirements and merge restrictions depend on branch protection rules or repository rulesets configured in GitHub repository settings. GitHub Free provides full support for protected branches and CODEOWNERS enforcement on public repositories; on private repositories, support for certain enforcement rules depends on the account's GitHub plan. (Adding `.github/CODEOWNERS` defines file ownership mapping, but actual enforcement must be enabled in GitHub repository settings).
