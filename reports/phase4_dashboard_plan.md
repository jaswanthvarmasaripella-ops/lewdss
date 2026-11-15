# Phase 4 Regional Landslide Decision Support Dashboard Plan
## LEWDSS — SIH26001 · CSE326/CSE276 Course Project
### Phase 4: Practical Decision Support Interface, Explainability Viewer, and Operational Limitations Plan
**Status: PROPOSAL & IMPLEMENTATION BLUEPRINT — AWAITING USER REVIEW**  
**Date: October 2026**  
**Author: Academic & Engineering Partner (SIH26001 Pair Programming)**  
**Audit Baseline: [`reports/phase3_results_audit.md`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/reports/phase3_results_audit.md)**

---

## 1. Executive Summary & Design Philosophy

Phase 4 defines the architecture and design plan for the user-facing **Regional Landslide Early Warning & Emergency Response Decision Support System (LEWDSS)** interface.

### 1.1 Strict Alignment with `AGENTS.md` Principles
In strict accordance with project principles:
- **Authentic Student-Built Disaster Monitoring Tool**: The UI must look like a practical, clean, engineering-focused decision support system built by civil/computer engineering students for district authorities, **not a generic AI-dashboard SaaS trope**.
- **No AI-Dashboard Tropes**: Eliminate neon gradients, dark cyberpunk glassmorphism, animated glowing cards, fake circular progress meters, and fabricated metrics (e.g. *"98.4% AI Accuracy"*).
- **No Fabricated Capabilities**: No claims of "real-time radar feeds", "satellite live telemetry", "verified collapse probabilities", or "autonomous evacuation routing".
- **Strict Ground Truth & Transparent Disclaimers**: Display the Phase 3 audit findings prominently, explicitly documenting weak folds, failed cross-region transfers, and Presence-Unlabeled evaluation boundaries.
- **Viva-Ready Architecture**: Keep the code clean, modular, and thoroughly commented so the student can explain every data flow, API route, and UI element during viva examination.

---

## 2. System Architecture & Zero-New-Dependency Design

To guarantee 100% stability and avoid dependency conflicts, Phase 4 requires **zero new package installations**. It utilizes Python's built-in standard library (`http.server`, `urllib`, `json`) alongside already verified packages (`joblib`, `numpy`, `pandas`).

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 LEWDSS ARCHITECTURE                                    │
└────────────────────────────────────────────────────────────────────────────────────────┘

 [ USER BROWSER ] 
        │
        ├──> Semantic HTML5 + Practical Vanilla CSS + Vanilla JS
        │    (No React/Vite/Tailwind bloat; authentic institutional styling)
        │
        ▼ (HTTP REST Requests)
 [ BACKEND SERVING LAYER — Python Standard Library ]
   file: api/server.py (BaseHTTPRequestHandler)
        │
        ├──> GET  /api/health               --> System status & test parity
        ├──> GET  /api/districts            --> 6 Target districts metadata & stats
        ├──> GET  /api/districts/{id}       --> District terrain, rainfall history, fold audit
        ├──> GET  /api/models/audit         --> Audited 48-run metrics from Phase 3 manifest
        ├──> GET  /api/explainability/{id}  --> Audited SHAP attribution & reference data
        └──> POST /api/predict/rlsi         --> Real-time RLSI calculation from frozen models
        │
        ▼ (Model & Data Assets)
 [ LOCAL DATA & CHECKPOINT ASSETS ]
   ├── models/checkpoints/               --> 48 Frozen .joblib pipelines (LR & RF)
   ├── data/processed/dataset_v1_features.csv --> 576 Audited sample records
   ├── data/raw/boundaries/target_districts.geojson --> District polygons
   ├── reports/phase3_experiment_results.json --> Audited metrics manifest
   └── reports/phase3_shap_summary.json       --> Audited SHAP feature rankings
```

### 2.1 Component Structure
```
LEWDSS Project Root
├── api/
│   ├── __init__.py
│   ├── server.py              # Lightweight stdlib HTTP server (REST API)
│   └── routers/
│       ├── __init__.py
│       ├── districts.py       # District terrain and historical catalog handlers
│       └── inference.py       # RLSI computation using frozen joblib checkpoints
├── frontend/
│   ├── index.html             # Clean, structured single-page application
│   ├── css/
│   │   ├── main.css           # Institutional design system (clean, legible, practical)
│   │   └── components.css     # District cards, RLSI gauge, SHAP bars, tables
│   ├── js/
│   │   ├── app.js             # Main controller, state management, tab routing
│   │   ├── district_view.js   # District terrain profiles and historical events
│   │   ├── rlsi_view.js       # RLSI classification and scenario testing
│   │   └── shap_view.js       # Feature attribution waterfall and explainability
│   └── assets/
│       └── icons/             # Simple SVG icons (hazard, terrain, rain, info)
├── src/
│   └── decision_support/
│       ├── __init__.py
│       ├── rlsi_engine.py     # Pure Python logic: thresholding & RLSI categorization
│       └── sop_guidance.py    # Institutional NDMA/DDMA preparedness advisories
└── tests/
    └── test_phase4_dashboard.py # Automated integration tests for API & RLSI logic
```

---

## 3. Core Dashboard Modules & UI Specifications

The dashboard will be organized into **four structured, purpose-built panels**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ LEWDSS: Regional Landslide Early Warning & Decision Support System (SIH26001)          │
│ Academic Research Prototype · CSE326/CSE276 Course Project · Master Seed: 42          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [Region A: Western Ghats]                     [Region B: Northeast Himalayas]          │
│  • Wayanad (KL)   • Idukki (KL)   • Kodagu (KA) │  • East Sikkim  • West Sikkim  • E. Khasi   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [Panel 1: District Profile]  [Panel 2: Historical Events]  [Panel 3: Model Assessment]  │
│ [Panel 4: SHAP Explainability & Physical Limitations]                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ ⚠ RESEARCH DISCLAIMER & AUDIT AUDIENCE BANNER (Always Visible)                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### Module 1: District Selection & Geographic Context Interface

The district selector provides direct access to the **six verified target districts**:
1. **Region A (Western Ghats — Peninsular Escarpment)**:
   - **Wayanad** (Kerala): 72 samples (18 positives, 54 background). Fold A1.
   - **Idukki** (Kerala): 204 samples (51 positives, 153 background). Fold A2.
   - **Kodagu** (Karnataka): 36 samples (9 positives, 27 background). Fold A3.
2. **Region B (Northeast — Himalayan Crystalline & Meghalaya Plateau)**:
   - **East Sikkim** (Sikkim): 60 samples (32 positives, 28 background). Fold B1.
   - **West Sikkim** (Sikkim): 68 samples (13 positives, 55 background). Fold B2.
   - **East Khasi Hills** (Meghalaya): 136 samples (21 positives, 115 background). Fold B3.

#### Display Elements per District:
- **Physiographic Belt**: Peninsular Pre-Cambrian Charnockite/Laterite vs. Himalayan Crystalline Nappe vs. Shillong Plateau.
- **Topographic Envelope**: Minimum, mean, and maximum elevation (from Copernicus DEM 30m).
- **Historical Inventory Footprint**: Total NASA GLC documented events ($n$), historical catalog date span (2007–2015).
- **Fold Audit Indicator**: Displays the empirical spatial cross-validation performance achieved on that specific held-out district in Phase 3.

---

### Module 2: Relative Landslide Susceptibility Index (RLSI) & Threshold Rules

#### 2.1 The RLSI Formulation
Model predictions represent an **Index of Relative Landslide Susceptibility (RLSI)**, scaled in the continuous interval $[0.0, 1.0]$. 
- It is **never** presented as an occurrence probability (e.g. *"78% chance of landslide tomorrow"*).
- It reflects relative hazard ranking compared to the regional landscape background envelope.

#### 2.2 Transparent Three-Tier Susceptibility Classification
Classification relies strictly on the **frozen training-selected decision threshold $\tau^*$** (derived to achieve $\ge 80\%$ recall on historical training data). For the primary operational model (**Logistic Regression FS2/FS3**, where $\tau^* \approx 0.46$):

| RLSI Category | Mathematical Range | Operational Meaning | Visual Encoding | Institutional Guidance |
|---|---|---|:---:|---|
| **Low Relative Susceptibility** | $\text{RLSI} < 0.50 \times \tau^*$ ($< 0.23$) | Terrain-rainfall conditions remain well within the baseline landscape background envelope. | Soft Green / Subtle Slate (`#2e7d32`) | Standard routine seasonal maintenance; ensure culverts and roadside drainage remain clear. |
| **Elevated Relative Susceptibility** | $0.50 \times \tau^* \le \text{RLSI} < \tau^*$ ($0.23 \le \text{RLSI} < 0.46$) | Cumulative rainfall or localized slope exceeds typical median background levels; approaches historical hazard thresholds. | Amber / Ochre (`#ed6c02`) | Heightened departmental vigilance; monitor active slope cuts; check vulnerable transport corridors. |
| **High Relative Susceptibility** | $\text{RLSI} \ge \tau^*$ ($\ge 0.46$) | Conditions meet or exceed the empirical decision threshold calibrated against known historical disaster events. | Crimson / Deep Orange (`#d32f2f`) | Issue district administrative advisory; verify family communication plans; prepare emergency resources. |

> [!IMPORTANT]
> **No Fabricated Confidence Percentages**:
> The UI will display the continuous score ($\text{RLSI} = 0.52$), the frozen threshold ($\tau^* = 0.46$), and the categorical tier (**High Relative Susceptibility**). It will **never** display pseudo-scientific confidence statements such as *"94.2% AI Confidence"*.

---

### Module 3: Plain-Language Feature Explanations & Model-Specific SHAP

#### 3.1 Plain-Language Feature Dictionary
The interface will provide an interactive feature glossary explaining each variable in non-academic terms:
- **Point Elevation (`elevation_m`)**: The terrain elevation above mean sea level extracted from the 30-meter Copernicus DEM.
- **Local Slope (`slope_deg`)**: The angle of the terrain inclination at the specific point. Slopes above $25^\circ\text{--}30^\circ$ represent mechanically critical thresholds in weathered soils.
- **Zonal Maximum Slope (`slope_max_1km`, `slope_max_3km`, `slope_max_5km`)**: The steepest slope found within a 1, 3, or 5 km radius. Captures steep escarpments and valley headwalls that may be nearby even if the recorded point is in a valley.
- **Elevation Relief (`elev_relief_1km`, `elev_relief_3km`, `elev_relief_5km`)**: The difference between the highest and lowest elevation within the buffer. Serves as a macro-topographic proxy for gravitational potential energy and catchment scale.
- **Antecedent Rainfall (`rain_3d_mm`, `rain_7d_mm`, `rain_15d_mm`)**: Cumulative rainfall over the preceding 3, 7, and 15 days from daily CHIRPS 0.05° satellite-gauge observations. Measures progressive soil pore-water accumulation.
- **Zonal Areal Mean Rainfall (`rain_3km_mean_3d`, `rain_3km_mean_7d`, `rain_3km_mean_15d`)**: Spatially averaged rainfall across a 3 km radius, buffering against localized satellite grid cell displacement.

#### 3.2 SHAP Explainability Viewer (Ground-Truth Models Only)
SHAP feature attributions will be rendered **strictly from the audited 12 analyses** in [`reports/phase3_shap_summary.json`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/reports/phase3_shap_summary.json):
- Displays horizontal bar charts of mean absolute SHAP values ($\text{Mean } |\text{SHAP}|$).
- Allows selecting between **Logistic Regression FS3** (`LinearExplainer`) and **Random Forest FS3** (`TreeExplainer`).
- **Attribution vs. Causation Warning Banner**:
  > *"SHAP attribution quantifies the mathematical weight assigned by the machine learning algorithm to input variables relative to the training landscape background. It does NOT prove physical geotechnical causation and does not measure subsurface pore pressure, soil cohesion, or rock fractures."*

---

### Module 4: Separation of Historical Observations vs. Model Predictions

To prevent confusion between historical ground truth and model estimations, the UI separates data into two distinct, clearly labeled tabs:

1. **Tab A: Historical Event Inventory & Observed Rainfall (Catalog Ground Truth)**:
   - Displays historical landslide records for the selected district from NASA GLC (2007–2015).
   - Shows recorded date, nearest known locality, documented trigger category, and the actual CHIRPS antecedent rainfall observed for that event ($R_{3\text{d}}, R_{7\text{d}}, R_{15\text{d}}$).
   - Clearly stamped: *"VERIFIED HISTORICAL DISASTER INVENTORY — STATIC OBSERVATIONAL DATA"*.
2. **Tab B: Scenario Assessment & Relative Susceptibility Estimator (Model Inference)**:
   - Allows users (or viva examiners) to inspect the model's response under historical rainfall scenarios or custom test inputs.
   - Computes the RLSI score using the **actual frozen model checkpoint for that district's outer spatial fold** (e.g. `LogisticRegression_FS3_Full_Fold_A1.joblib` for Wayanad).
   - Displays the confusion matrix outcome ($TP, FP, FN, TN$) achieved by that model on that held-out district.
   - Clearly stamped: *"EXPERIMENTAL RELATIVE HAZARD ESTIMATION — NOT A REAL-TIME WARNING"*.

---

### Module 5: Prominent Scientific Limitations & Weak-Fold Disclosure

An institutional decision support system must be transparent about its weaknesses. The dashboard will include a permanent **"Scientific Integrity & Limitations"** drawer / footer detailing the exact findings from the Phase 3 results audit:

1. **Fold B3 (East Khasi Hills) Limitation**:
   - Transparently discloses that in East Khasi Hills, the models achieved near-random discrimination ($\text{ROC-AUC} = 0.430\text{--}0.453$).
   - Explains that Meghalaya's flat-topped karst and sandstone plateau structure exhibits fundamentally different failure mechanics than the steep crystalline Himalayas of Sikkim.
2. **Fold A3 (Kodagu) Small-Sample Limitation**:
   - Notes that Kodagu contains only 9 documented events in the inventory. While Logistic Regression achieved $66.7\%$ recall (detecting 6 of 9), Random Forest achieved $0.0\%$ recall due to severe probability threshold mismatch.
3. **Random Forest Threshold Miscalibration**:
   - Explicitly discloses that Random Forest failed the $80\%$ operational recall target across 100% of spatial folds (average recall $15.4\%\text{--}34.0\%$), explaining that uncalibrated tree probabilities collapse under spatial domain shift.
4. **Cross-Region Transfer Domain Gap**:
   - Highlights that models trained in the Western Ghats failed completely when transferred to the Himalayas ($\text{Recall} = 40.9\%\text{--}47.0\%$), and vice-versa, demonstrating that models cannot be transferred between disparate mountain belts without local recalibration.
5. **Presence-Unlabeled Evaluation Scope**:
   - Clarifies that reported Precision and F1 scores are evaluated against 5 km-buffered landscape background points, not confirmed stable ground, and must not be cited as real-world occurrence accuracy.

---

### Module 6: Practical Preparedness Guidance (Institutional NDMA/DDMA Alignment)

All recommendations will be framed as **advisory standard operating procedures**, never as autonomous evacuation commands:

- **Institutional Protocol Disclaimer**:
  > *"LEWDSS is an academic decision support prototype. It is NOT an official alerting authority. All evacuation orders, hazard alerts, and emergency management actions are strictly governed by the National Disaster Management Authority (NDMA), State Disaster Management Authorities (SDMAs), and District Disaster Management Authorities (DDMAs)."*

- **Practical SOP Guidance Cards**:
  - **Community Level**: Maintain drainage channels free of organic blockage; inspect retaining walls for fresh tension cracks; report localized slope bulging to gram panchayat officials.
  - **Transport / Infrastructure**: Exercise caution on steep road cuttings along national and state highways during continuous rainfall exceeding $150\text{ mm} / 15\text{ days}$.
  - **Administrative Level**: Review emergency shelter readiness; verify satellite phone communication links in remote taluks; monitor IMD district weather bulletins.

---

## 4. Implementation Steps & Verification Plan

### Phase 4.1: Backend Server & Decision Support Logic (Python Standard Library)
1. Implement `src/decision_support/rlsi_engine.py`:
   - Categorization logic: maps raw continuous score and $\tau^*$ to Low, Elevated, or High tier.
   - Loads model checkpoints safely via `joblib.load()`.
2. Implement `src/decision_support/sop_guidance.py`:
   - Structured dictionary of general institutional preparedness measures mapped to hazard tiers.
3. Implement `api/server.py`:
   - Python stdlib `http.server.BaseHTTPRequestHandler`.
   - Handles static file serving for `frontend/` directory.
   - Implements JSON REST endpoints: `/api/health`, `/api/districts`, `/api/explainability`, `/api/predict/rlsi`.

### Phase 4.2: Frontend Interface Development (Vanilla Web Technologies)
1. Build `frontend/index.html`:
   - Accessible, semantic HTML5 structure with clear ARIA labels and single `<h1>`.
   - Four dedicated panel sections with tabbed navigation.
2. Build `frontend/css/main.css` & `frontend/css/components.css`:
   - Clean, institutional, readable design system (system font stack, high-contrast typography, subdued card borders, muted status chips).
   - Zero AI-dashboard tropes (no pulsing neon circles, no artificial dark-glass cards).
3. Build `frontend/js/app.js`, `district_view.js`, `rlsi_view.js`, `shap_view.js`:
   - Dynamic district selection and scenario evaluation.
   - Pure vanilla JavaScript with zero third-party framework dependencies.

### Phase 4.3: Testing & Verification
1. Create `tests/test_phase4_dashboard.py`:
   - Test RLSI categorization logic and boundary conditions.
   - Test threshold application parity against Phase 3 checkpoints.
   - Test API route handlers and payload schemas.
   - Test static asset availability.
2. Run full test suite (`pytest`) to confirm all 186 existing tests + new dashboard tests pass cleanly.

---

## 5. Viva Defense Alignment Checklist for Phase 4

| Viva Examination Topic | How Phase 4 Implements and Defends It |
|---|---|
| **Authenticity vs. AI Dashboard Tropes** | The interface uses clean institutional typography, practical emergency management cards, and factual data tables. No neon gradients, no meaningless metrics, and no simulated animations. |
| **Why RLSI instead of Landslide Probability?** | Documented on the dashboard: Natural disaster records lack verified negative points (PU problem). RLSI ranks relative susceptibility against background; claiming calibrated real-world probabilities is scientifically fraudulent. |
| **Why does the dashboard report failed folds?** | Following scientific integrity (`AGENTS.md`), the dashboard prominently shows East Khasi Hills' weak ROC-AUC and Random Forest's threshold failure, proving the student understands real-world machine learning limitations. |
| **How does SHAP explain decisions?** | The dashboard renders verified SHAP values from training-fold background reference distributions, while explicitly warning that SHAP is statistical attribution, not geotechnical slope stability. |
| **Why are evacuation orders omitted?** | Academic software cannot legally or ethically order evacuations. The system provides general NDMA/DDMA preparedness advisories for decision support only. |
| **Zero New Package Installations** | Uses Python's built-in `http.server` and lightweight Vanilla JavaScript. Fully reproducible on any standard Python 3.11+ environment without complex setup. |
