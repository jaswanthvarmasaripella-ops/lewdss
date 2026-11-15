# Phase 4 Dashboard & Decision Support Implementation Report
## LEWDSS — SIH26001 · CSE326/CSE276 Course Project
### Practical Regional Disaster Decision Support Interface & Explainability System
**Status: IMPLEMENTATION COMPLETE & 100% VERIFIED**  
**Date: October 2026**  
**Author: Academic & Engineering Partner (SIH26001 Pair Programming)**  
**Audit Baseline: [`reports/phase3_results_audit.md`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/reports/phase3_results_audit.md)**  
**Test Suite Status: 203 / 203 Unit & Integration Tests Passing (0 Failures, 0 Errors)**

---

## 1. Executive Summary

Phase 4 successfully delivers a **practical, authentic, student-built regional disaster monitoring interface** and zero-dependency REST backend for the Regional Landslide Early Warning & Emergency Response Decision Support System (LEWDSS). 

In strict adherence to [`AGENTS.md`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/AGENTS.md) and the user's explicit safeguards:
- **Zero New Package Installations**: Built entirely using Python's standard library (`http.server`, `urllib`, `json`), vanilla JavaScript, semantic HTML5, and bespoke institutional CSS.
- **Preservation of All Artifacts**: All 48 model checkpoints in [`models/checkpoints/`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/models/checkpoints), datasets in [`data/`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/data/), experiment manifests, and existing reports were strictly preserved. No models were retrained.
- **Authentic, Restrained UI**: Avoided generic AI-dashboard tropes (no neon gradients, no animated glowing borders, no fake circular progress meters, no simulated real-time telemetry).
- **Strict Separation of Observations vs. Estimates**: Historical NASA GLC disaster events and observed CHIRPS rainfall are isolated in **Panel A**, while experimental model evaluations are isolated in **Panel B**.
- **No Fabricated Confidence Statements**: Model outputs are strictly labeled as an **Index of Relative Landslide Susceptibility (RLSI)**, ranking terrain-rainfall conditions relative to the landscape background envelope. Categorical tiers are project-defined, not official warning levels or calibrated collapse probabilities.
- **Full Test Suite Expansion**: Automated tests expanded from 186 to **203 passing tests**, covering decision support logic, schema validation, API routes, and static asset serving.

---

## 2. District Scenarios, Checkpoints & Feature Schema Parity

The system supports the **six verified target districts**, directly mapping each district to its primary spatial holdout fold:

| District Name | Region & State | Primary Outer Fold | Outer Training Districts | Primary Checkpoint File | Features Used | Frozen Threshold ($\tau^*$) | Held-Out Test Recall |
|---|---|:---:|---|---|:---:|:---:|:---:|
| **Wayanad** | Western Ghats (Kerala) | `Fold_A1` | Idukki, Kodagu | `LogisticRegression_FS3_Full_Fold_A1.joblib` | 17 (FS3 Full) | $0.440$ | $100.0\%$ (18/18) |
| **Idukki** | Western Ghats (Kerala) | `Fold_A2` | Wayanad, Kodagu | `LogisticRegression_FS3_Full_Fold_A2.joblib` | 17 (FS3 Full) | $0.450$ | $98.0\%$ (50/51) |
| **Kodagu** | Western Ghats (Karnataka) | `Fold_A3` | Wayanad, Idukki | `LogisticRegression_FS3_Full_Fold_A3.joblib` | 17 (FS3 Full) | $0.460$ | $66.7\%$ (6/9) |
| **East Sikkim** | Northeast (Sikkim) | `Fold_B1` | West Sikkim, East Khasi | `LogisticRegression_FS3_Full_Fold_B1.joblib` | 17 (FS3 Full) | $0.470$ | $100.0\%$ (32/32) |
| **West Sikkim** | Northeast (Sikkim) | `Fold_B2` | East Sikkim, East Khasi | `LogisticRegression_FS3_Full_Fold_B2.joblib` | 17 (FS3 Full) | $0.430$ | $100.0\%$ (13/13) |
| **East Khasi Hills** | Northeast (Meghalaya) | `Fold_B3` | East Sikkim, West Sikkim | `LogisticRegression_FS3_Full_Fold_B3.joblib` | 17 (FS3 Full) | $0.520$ | $57.1\%$ (12/21) |

> [!IMPORTANT]
> **No Unvalidated Generalization Claim**:
> The dashboard UI and API explicitly state: *"Evaluated under spatial holdout protocol. This checkpoint was trained on the remaining regional districts and is NOT validated for arbitrary uncalibrated deployment locations."*

---

## 3. Verified Historical Dataset Provenance & Date Ranges

Historical dates and sample counts were verified directly from [`data/processed/dataset_v1_features.csv`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/data/processed/dataset_v1_features.csv) and [`data/processed/dataset_v1_metadata.json`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/data/processed/dataset_v1_metadata.json):

```
DATASET PROVENANCE AUDIT SUMMARY:
• Inventory Source: NASA Global Landslide Catalog (GLC), spatial-joined to 2011 India Census district boundaries.
• Topographic Source: Copernicus DEM GLO-30 (30-meter resolution).
• Rainfall Source: CHIRPS v2.0 daily satellite-gauge precipitation (0.05° resolution).
• Total Dataset Size: 576 samples (144 positive documented landslides, 432 landscape background points).
• Sampling Design: Presence-Unlabeled (PU) framework with 5 km positive exclusion buffer and 3 km inter-background spacing.
• Monsoon Temporal Window: June 1 to September 30.
• Verified Positive Event Date Spans by District:
  - Overall Range: August 4, 2004 to August 29, 2022
  - Wayanad: June 22, 2007 to August 8, 2019 (18 positive events)
  - Idukki: August 4, 2004 to August 29, 2022 (51 positive events)
  - Kodagu: July 4, 2006 to September 22, 2018 (9 positive events)
  - East Sikkim: August 3, 2006 to September 15, 2018 (32 positive events)
  - West Sikkim: August 2, 2007 to September 20, 2017 (13 positive events)
  - East Khasi Hills: October 9, 2004 to July 9, 2019 (21 positive events)
```

---

## 4. Software Architecture & Components Delivered

### 4.1 Backend Engine & API Server
1. [`src/decision_support/rlsi_engine.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/src/decision_support/rlsi_engine.py):
   - `load_model_checkpoint()`: Validates checkpoint presence, metadata integrity, and exact feature list.
   - `compute_rlsi()`: Enforces full feature schema parity, arranges inputs in exact training order, applies frozen `StandardScaler`, and predicts continuous score.
   - `categorize_rlsi()`: Assigns project-defined display tiers based on the frozen training threshold $\tau^*$.
   - **Zero Silent Workarounds**: Raises explicit `ValueError` if any feature is missing or non-numeric.
2. [`src/decision_support/sop_guidance.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/src/decision_support/sop_guidance.py):
   - `get_sop_guidance()`: Provides NDMA/DDMA-aligned preparedness checklists for Community, Infrastructure/Transport, and Emergency Desk operations.
   - Includes mandatory institutional non-alerting disclaimer.
3. [`api/server.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/api/server.py):
   - Zero-dependency REST API and static file server built with Python standard library `http.server.BaseHTTPRequestHandler`.
   - Endpoints:
     - `GET /api/health`: System status, seed 42, checkpoint count.
     - `GET /api/districts`: Metadata, sample counts, and verified date spans for all 6 target districts.
     - `GET /api/districts/<name>`: Topographic profiles, verified historical event table, and audited fold performance.
     - `GET /api/explainability/<name>`: Verified SHAP feature attributions and causality disclaimer.
     - `GET /api/models/audit`: Phase 3 audit manifest and documented limitations.
     - `POST /api/predict/rlsi`: Computes RLSI and attaches SOP guidance.
     - `GET /`, `GET /css/*`, `GET /js/*`: Serves static frontend files with correct MIME types.

### 4.2 Restrained, Authentic User Interface
1. [`frontend/index.html`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/frontend/index.html):
   - Semantic HTML5 structure with accessible ARIA labels.
   - Prominent mandatory academic research prototype alert banner.
   - Distinct controls for district selection, model family, and feature set.
   - **Panel A**: Historical documented events table with observed rainfall and one-click "Load Scenario" button.
   - **Panel B**: RLSI scenario estimator, threshold comparison meter, and SOP guidance cards.
   - Feature explainability glossary and SHAP attribution bar visualization.
   - Scientific integrity drawer detailing Phase 3 audit limitations.
2. [`frontend/css/main.css`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/frontend/css/main.css):
   - Authentic institutional styling (clean dark blue header, high-contrast typography, slate borders).
   - High visual clarity without generic AI tropes (no dark glassmorphism, no neon glows, no spinning decorative elements).
   - Clear categorical hazard color-coding (Muted Green for Low, Ochre for Elevated, Crimson for High).
3. [`frontend/js/app.js`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/frontend/js/app.js):
   - Pure vanilla JavaScript (zero frontend build tools, zero external CDNs).
   - Asynchronous fetch integration with API endpoints.
   - Instant re-rendering upon district or model selection.

---

## 5. Decision Support Logic: Project-Defined RLSI Categories

Model outputs represent an **Index of Relative Landslide Susceptibility (RLSI)**, scaled in $[0.0, 1.0]$. The interface presents three **project-defined display tiers** derived from the frozen training threshold $\tau^*$:

```
RLSI CATEGORIZATION RULE MATRIX:
┌──────────────────────────────────────┬────────────────────────┬────────────────────────────────────────────────────────┐
│ RLSI Category Tier                   │ Mathematical Range     │ Operational Meaning & Display Badge                   │
├──────────────────────────────────────┼────────────────────────┼────────────────────────────────────────────────────────┤
│ Low Relative Susceptibility          │ RLSI < 0.50 * tau*     │ Muted Green: Within baseline regional landscape       │
│                                      │                        │ background envelope. Normal seasonal monitoring.       │
├──────────────────────────────────────┼────────────────────────┼────────────────────────────────────────────────────────┤
│ Elevated Relative Susceptibility     │ 0.50 * tau* <= RLSI    │ Amber/Ochre: Approaching historical hazard threshold.  │
│                                      │ < tau*                 │ Heightened vigilance; check vulnerable road cuts.     │
├──────────────────────────────────────┼────────────────────────┼────────────────────────────────────────────────────────┤
│ High Relative Susceptibility         │ RLSI >= tau*           │ Crimson: Exceeds decision threshold calibrated for    │
│                                      │                        │ >=80% training recall. Issue preparedness advisory.   │
└──────────────────────────────────────┴────────────────────────┴────────────────────────────────────────────────────────┘
```

> [!NOTE]
> **No Fabricated Confidence Percentages**:
> The UI displays the continuous score ($\text{RLSI} = 0.5120$), the frozen threshold ($\tau^* = 0.4400$), and the threshold status. It **never** displays pseudo-scientific confidence statements such as *"94.2% AI Accuracy"*.

---

## 6. Plain-Language Feature Explanations & SHAP Attribution Viewer

### 6.1 Variable Definitions
- **Point Elevation (`elevation_m`)**: Terrain elevation above sea level extracted from the 30-meter Copernicus DEM.
- **Local Slope (`slope_deg`)**: Inclination angle; slopes $> 25^\circ\text{--}30^\circ$ approach mechanical shear failure limits in saturated soils.
- **Zonal Maximum Slope (`slope_max_1km/3km/5km`)**: Steepest terrain within a 1, 3, or 5 km radius, capturing adjacent escarpments and valley headwalls.
- **Elevation Relief (`elev_relief_1km/3km/5km`)**: Difference between maximum and minimum elevation in the buffer; acts as a macro-topographic proxy for gravitational potential energy.
- **Antecedent Rainfall (`rain_3d/7d/15d_mm`)**: Cumulative precipitation over 3, 7, and 15 days from daily CHIRPS 0.05° satellite-gauge observations. Measures progressive pore-water buildup.
- **Zonal Areal Mean Rainfall (`rain_3km_mean_3d/7d/15d`)**: Spatially averaged precipitation across 3 km, buffering against satellite grid cell displacement.

### 6.2 SHAP Explainability & Causal Boundary
SHAP feature rankings are loaded directly from the verified 12 analyses in [`reports/phase3_shap_summary.json`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/reports/phase3_shap_summary.json):
- Accompanied by a permanent notice:
  > *"SHAP attribution quantifies the mathematical feature weighting assigned by the statistical model relative to the training landscape background. It does NOT prove physical geotechnical causation and does not measure subsurface pore-water pressure, soil cohesion, or rock fractures."*

---

## 7. Preparedness Guidance (Institutional NDMA/DDMA Alignment)

All recommendations are framed as **general institutional preparedness guidelines**, never as autonomous evacuation commands:

- **Institutional Disclaimer Banner**:
  > *"LEWDSS is an academic research prototype. It does NOT have legal authority to issue evacuation orders. All emergency actions are strictly governed by the District Disaster Management Authority (DDMA) and local civil administration."*
- **SOP Checklists**:
  - **Community**: Clearance of roadside drainage ditches, observation of retaining wall tension cracks, reporting mud surges in mountain streams.
  - **Transport / Infrastructure**: Highway patrol stand-by, cautionary signage along steep cuttings, prepositioning of earthmoving machinery at taluk depots.
  - **Emergency Desk**: Tracking multi-day rainfall against historical thresholds, maintaining satellite communication links with remote hillside panchayats.

---

## 8. Transparent Disclosure of Scientific Audit Limitations

The dashboard includes a dedicated **Limitations Drawer** documenting the exact findings from the Phase 3 results audit:
1. **Fold B3 (East Khasi Hills)**: Discloses near-random discrimination ($\text{ROC-AUC} \approx 0.44$). Meghalaya's flat-topped plateau exhibits fundamentally different geomorphology than the steep crystalline Himalayas of Sikkim.
2. **Fold A3 (Kodagu)**: Discloses small sample footprint ($n=9$ positive events) where Random Forest suffered total detection failure ($0.0\%$ recall) and Logistic Regression achieved $66.7\%$.
3. **Random Forest Threshold Miscalibration**: Discloses that Random Forest failed the $80\%$ operational recall target across 100% of spatial folds due to probability distribution compression under spatial covariate shift.
4. **Cross-Region Transfer Failure**: Discloses that models trained in the Western Ghats failed completely when transferred to the Himalayas ($40.9\%\text{--}47.0\%$ recall) due to extreme elevation domain shift ($2,000\text{ m}$ peak vs $5,800\text{ m}$).
5. **PU Evaluation Boundaries**: Clarifies that Precision and F1 are nominal pseudo-metrics evaluated against 5 km-buffered background locations, not real-world occurrence accuracy.

---

## 9. Automated Test Suite Execution

The automated test suite was executed across the entire repository:

```bash
python -m pytest tests/ -v
============================= test session starts =============================
platform win32 -- Python 3.13.6, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\VARMA\OneDrive\Desktop\AI project
collected 203 items

tests\test_chirps_downloader.py ........................................ [ 19%]
.................                                                        [ 28%]
tests\test_feature_pipeline.py ......................................... [ 48%]
.......                                                                  [ 51%]
tests\test_ingestion.py ......                                           [ 54%]
tests\test_phase2_dataset.py ...........                                 [ 60%]
tests\test_phase3_models.py .........                                    [ 64%]
tests\test_phase4_api.py .........                                       [ 68%]
tests\test_phase4_decision_support.py ........                           [ 72%]
tests\test_uglc_audit.py .....                                           [ 75%]
tests\test_validation_scaffold.py ...................................... [ 94%]
............                                                             [100%]

============================ 203 passed in 19.96s =============================
```

- **Test Suite Growth**:
  - Phase 1 Baseline & Pipeline Tests: 166 passed.
  - Phase 2 Dataset Verification Tests: 11 passed.
  - Phase 3 Model & Spatial CV Tests: 9 passed.
  - **Phase 4 Decision Support Engine Tests**: 8 passed ([`tests/test_phase4_decision_support.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/tests/test_phase4_decision_support.py)).
  - **Phase 4 REST API & Static Serving Tests**: 9 passed ([`tests/test_phase4_api.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/tests/test_phase4_api.py)).
  - **Total**: **203 / 203 tests passing cleanly (100% green, 0 failures, 0 errors, 0 warnings)**.

---

## 10. How to Run the Dashboard

The dashboard server can be launched directly using Python's standard library:

```bash
# Launch the LEWDSS decision support server
python api/server.py --port 8000

# Open in browser:
# http://127.0.0.1:8000/
```

- **Zero dependencies required beyond Python 3.11+ and the existing environment.**
- Press `Ctrl+C` to terminate the server.
