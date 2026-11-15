# LEWDSS — Landslide Early-Warning Decision Support System
## SIH26001 · CSE326/CSE276 Course Project
### Regional Landslide Risk & Emergency Response Decision System

> **⚠️ ADVISORY PROTOTYPE — NOT FOR OPERATIONAL USE**
> All outputs of this system are advisory only. They are not operationally
> validated predictions. See Blueprint v2.0 for full disclaimer.

---

## Current Milestone: M0 — Data Reconnaissance

The project is in **Milestone M0**. No models have been trained, no data has been
downloaded. The purpose of this milestone is to:

1. Establish the reproducible project environment
2. Verify which public datasets are actually accessible and legally usable
3. Count available events and determine task framing (occurrence vs. susceptibility)
4. Make all data decisions before writing model code

**Do not proceed to Phase 1 until `reports/data_reconnaissance_report.md` is complete
and approved.**

---

## Setup Instructions

### Prerequisites

- Python 3.11 or higher (tested on 3.13.6)
- pip 23+
- Internet connection (for reconnaissance URL probing)
- Optional: conda (for environment management)

### Step 1 — Install dependencies

```powershell
# Using pip (recommended for this system)
pip install -r requirements.txt

# Or using conda (if available)
conda env create -f environment.yml
conda activate lewdss
```

### Step 2 — Verify installation

```powershell
# Quick Python verification
python -c "import numpy, pandas, requests, yaml, pytest; print('All M0 core imports OK')"

# Using PowerShell runner (Windows)
.\run.ps1 check-env

# Or using Makefile (Linux/macOS or Windows with make)
make check-env
```

Expected output:
```
--- Checking Environment ---
Python:   3.13.x
numpy:    2.x.x
pandas:   3.x.x
requests: 2.x.x
pyyaml:   OK
pytest:   9.x.x

[OK] Environment check passed.
```

### Step 3 — Run M0 tests (no data required)

```powershell
# Using pytest directly
python -m pytest tests/ -v

# Or using PowerShell runner
.\run.ps1 test-m0

# Or dry-run validation scaffold only
.\run.ps1 validate-dry
```

All 54 tests should pass. They use synthetic in-memory DataFrames — no downloads needed.

### Step 4 — Open the reconnaissance notebook

You can open `notebooks/00_data_reconnaissance.ipynb` directly in your IDE (VS Code, Cursor, PyCharm), or if Jupyter is installed:

```powershell
jupyter notebook notebooks/00_data_reconnaissance.ipynb
# Or: .\run.ps1 reconn
```

Run all cells. Fill in the results in `reports/data_reconnaissance_report.md`.

---

## Project Structure

```
landslide-risk-system/
├── configs/
│   └── config.yaml              ← All parameters, seeds, thresholds
├── data/
│   ├── raw/                     ← Downloaded files (not committed to git)
│   │   ├── region_a/            ← Western Ghats
│   │   └── region_b/            ← Northeast India
│   ├── interim/                 ← Intermediate processed files
│   └── processed/               ← Final ML-ready CSVs
├── notebooks/
│   ├── 00_data_reconnaissance.ipynb  ← START HERE
│   ├── 01_data_exploration.ipynb
│   ├── 02_feature_engineering.ipynb
│   ├── 03_model_training.ipynb
│   ├── 04_shap_analysis.ipynb
│   └── 05_state_space_modeling.ipynb
├── src/
│   ├── data/
│   │   ├── ingestion.py         ← Safe download helpers (dry_run=True by default)
│   │   └── validation.py        ← 12 data quality checks
│   ├── features/                ← Phase 2+
│   ├── models/                  ← Phase 3+
│   ├── explainability/          ← Phase 4+
│   ├── state_space/             ← Phase 5+
│   └── decision_support/        ← Phase 6+
├── api/                         ← Phase 6+
├── frontend/                    ← Phase 7+
├── models/                      ← Saved model artifacts (Phase 3+)
├── tests/
│   └── test_validation_scaffold.py  ← M0 tests (no data required)
├── reports/
│   └── data_reconnaissance_report.md  ← Fill in during M0
├── environment.yml
├── requirements.txt
├── Makefile
└── README.md
```

---

## Makefile Targets

| Target | Description | Phase |
|---|---|---|
| `make install` | Install M0 dependencies | M0 |
| `make check-env` | Verify Python + imports | M0 |
| `make reconn` | Open reconnaissance notebook | M0 |
| `make validate-dry` | Run validation scaffold tests | M0 |
| `make test-m0` | Run all M0 tests | M0 |
| `make test` | Run full test suite with coverage | M1+ |
| `make preprocess` | *(LOCKED)* Run preprocessing pipeline | Phase 2 |
| `make train` | *(LOCKED)* Train models | Phase 3 |
| `make evaluate` | *(LOCKED)* Run evaluation | Phase 3 |
| `make api` | *(LOCKED)* Start API server | Phase 6 |

**Windows**: use `nmake -f Makefile <target>`
**Linux/macOS**: use `make <target>`

---

## Data Sources Under Investigation

All sources are **candidates only** — none have been verified as accessible yet.
See `reports/data_reconnaissance_report.md` for verification status.

| Source | Type | Access | Priority |
|---|---|---|---|
| NASA Global Landslide Catalog | CSV | Open | Primary events |
| ISRO Bhuvan Landslide Atlas | Shapefile | Portal | Supplementary events |
| CHIRPS v2.0 | Raster (daily rain) | Open | Primary rainfall |
| Copernicus DEM GLO-30 | Raster | Open | Primary DEM |
| NASA SMAP L3 | NetCDF | EarthData login | Soil moisture Tier 1 |
| GLEAM v3 | NetCDF | Registration | Soil moisture Tier 2 |
| HWSD v2 (FAO) | Raster | Open | Soil texture + Tier 3 SM |
| NOAA GFS | GRIB2 | Open | DLM forecast (optional) |
| GSI Bhukosh | Shapefile | Portal (license TBD) | Geology |
| India District Boundaries | GeoJSON | Open | Unit of analysis |

---

## Two Geographic Regions

| Region | States | Key Districts |
|---|---|---|
| **Region A** — Western Ghats | Karnataka, Kerala, Maharashtra | Kodagu, Wayanad, Idukki, Ratnagiri, Kollam |
| **Region B** — Northeast India | Sikkim, Meghalaya | East Sikkim, West Sikkim, East Khasi Hills, Ri Bhoi |

---

## Reproducibility

- All random seeds set via `configs/config.yaml` → `seed: 42`
- All scripts will accept `--seed` CLI argument
- `environment.yml` documents conda environment (pip fallback: `requirements.txt`)
- SHA-256 checksums for all downloaded files logged in `reports/data_reconnaissance_report.md`
- Notebook outputs cleared before git commit

---

## Development Phases

| Phase | Status | Description |
|---|---|---|
| M0 | **IN PROGRESS** | Environment + reconnaissance |
| Phase 1 | LOCKED | Data acquisition + validation |
| Phase 2 | LOCKED | Preprocessing + feature engineering |
| Phase 3 | LOCKED | Model training (LR + RF) + spatial CV |
| Phase 4 | LOCKED | SHAP explainability |
| Phase 5 | LOCKED | State-space DLM |
| Phase 6 | LOCKED | FastAPI backend |
| Phase 7 | LOCKED | Frontend dashboard |
| Phase 8 | LOCKED | Integration testing |

---

## Validation Checks

The `src/data/validation.py` module implements 12 checks from Blueprint v2.0 §18:

| # | Check | Category | Requires Data? |
|---|---|---|---|
| 1 | Schema check | A | No |
| 2 | CRS consistency | B | Yes (spatial files) |
| 3 | Null fraction | A | No |
| 4 | Value ranges | A | No |
| 5 | Duplicate keys | A | No |
| 6 | Spatial bounds | A | No (with centroids) |
| 7 | Catalog crosswalk | B | Yes (event catalog) |
| 8 | Date precision | B | Yes (event catalog) |
| 9 | Class imbalance | A | No |
| 10 | Temporal coverage | B | Yes (rainfall + SM) |
| 11 | DEM void check | B | Yes (DEM extraction) |
| 12 | SM tier consistency | A | No |

**Category A checks** run immediately with mock data (tested in M0 test suite).
**Category B checks** return SKIP status until real data is available.

---

## Advisory Disclaimer

> This system is a **research prototype** for the CSE326/CSE276 course project.
> All outputs are advisory only, intended to inform human judgment.
> Model probabilities are not operationally validated.
> No evacuation orders or operational directives should be based solely on
> this system's outputs. All emergency decisions must be made by qualified
> authorities following official SDMA/NDRF protocols.

---

*Blueprint v2.0 · Milestone M0 · SIH26001*
