# Phase 3 Model Experiment & Spatial Cross-Validation Plan
## LEWDSS — SIH26001 · CSE326/CSE276 Course Project
### Phase 3: Spatial Cross-Validation, Baseline Modeling, and Explainability Plan
**Status: REVISED EXPERIMENTAL DESIGN — APPROVED METHODOLOGICAL PROTOCOL PRIOR TO TRAINING**
**Date: October 2026**

---

> [!IMPORTANT]
> **Academic Integrity & Methodological Scope Notice**
> This document specifies the comprehensive experimental plan for Phase 3 model training, validation, and explainability.
> - **No machine learning models have been trained yet.**
> - **No model metrics, accuracies, or SHAP values are invented or simulated.**
> - **No new packages or external datasets have been downloaded.**
> - Model outputs will represent an **Index of Relative Landslide Susceptibility (RLSI)** under a formal Presence-Unlabeled (PU) framework, **never** a "calibrated real-world probability of imminent landslide occurrence".
> - All baseline files and dataset assets remain strictly preserved.

---

## 1. Dataset v1 Audit & Sampling Discrepancy Resolution

### 1.1 Dataset Audit Verification

The generated Phase 2 dataset ([`data/processed/dataset_v1_features.csv`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/data/processed/dataset_v1_features.csv)) was subjected to a rigorous row-level audit against all approved sampling constraints:

| Constraint | Evaluation Scope | Measured Value | Standard Required | Audit Outcome |
|---|---|:---:|:---:|:---:|
| **Global 5 km Positive Exclusion** | All 432 background points vs. all 144 positives | Measured min: **$5.008\text{ km}$** | Distance $\ge 5.0\text{ km}$ globally | **VERIFIED (0 violations)** |
| **Global 3 km Inter-Background Spacing** | All pairwise background combinations | Measured min: **$3.004\text{ km}$** | Distance $\ge 3.0\text{ km}$ globally | **VERIFIED (0 violations)** |
| **Polygon Containment** | All 576 samples against GeoJSON | **576 / 576 (100.0%)** | Strict in-polygon | **VERIFIED (0 violations)** |
| **Unique Positive Event IDs** | 144 positive records | **144 unique IDs** | Exactly 144 unique IDs | **VERIFIED (0 duplicates)** |
| **Date-Paired Co-occurrence** | 432 background samples | **432 / 432 valid** | Verified 15-day CHIRPS crop | **VERIFIED (100% complete)** |
| **Feature Completeness** | All 28 columns across 576 rows | **0 missing values** | Zero nulls/sentinels | **VERIFIED (100% complete)** |

### 1.2 Discrepancy Resolution & Code Hardening

During audit inspection, an architectural refinement was identified and implemented in [`src/features/background_sampler.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/src/features/background_sampler.py):
- **Observation**: The initial sampler loop checked distance against positive events within the same district (`d_positives`). While the generated dataset with seed 42 had zero cross-district violations by virtue of district separation, re-running with arbitrary seeds could theoretically allow a border background sample in one district to fall within $5\text{ km}$ of a positive event in an adjacent district (e.g. Wayanad vs. Kodagu).
- **Resolution**: `background_sampler.py` was hardened to explicitly check candidate coordinates against **`all_pos_coords` (all 144 positives globally)** and **`all_background_samples` (all background points globally across all districts)**.
- **Verification**: Re-running automated tests ([`tests/test_phase2_dataset.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/tests/test_phase2_dataset.py)) confirmed **11/11 tests pass**, and the full project suite (**177 tests**) passes cleanly.

---

## 2. Reproducible Spatial Cross-Validation Plan

### 2.1 The Spatial Autocorrelation Hazard (Viva Defense Key)

Standard random $k$-fold cross-validation randomly shuffles samples into folds. For geospatial phenomena, this produces **severe data leakage**: training and test folds contain points separated by only a few hundred meters. The model memorizes spatial proximity rather than learning generalizable terrain and rainfall relationships, resulting in artificially inflated validation scores ($> 95\%$) that collapse in real-world deployment.

To ensure scientific validity and viva defensibility, Phase 3 implements an **explicit two-tier spatial validation architecture**.

```
SPATIAL VALIDATION ARCHITECTURE:

Level 1: Within-Region Spatial Group CV (Leave-One-District-Out)
┌──────────────────────────────────────────────────────────────────────────────────┐
│ REGION A (Western Ghats — 312 samples):                                          │
│   Fold A1: Train on [Idukki (204) + Kodagu (36)]        --> Test on [Wayanad (72)]│
│   Fold A2: Train on [Wayanad (72) + Kodagu (36)]        --> Test on [Idukki (204)]│
│   Fold A3: Train on [Wayanad (72) + Idukki (204)]       --> Test on [Kodagu (36)] │
│                                                                                  │
│ REGION B (Northeast Himalayas — 264 samples):                                    │
│   Fold B1: Train on [West Sikkim (68) + E. Khasi (136)] --> Test on [E. Sikkim (60)]│
│   Fold B2: Train on [East Sikkim (60) + E. Khasi (136)] --> Test on [W. Sikkim (68)]│
│   Fold B3: Train on [East Sikkim (60) + W. Sikkim (68)] --> Test on [E. Khasi (136)]│
└──────────────────────────────────────────────────────────────────────────────────┘

Level 2: Cross-Region Transferability Benchmark (Domain Adaptation)
┌──────────────────────────────────────────────────────────────────────────────────┐
│   Experiment TR-1: Train on Region A (Western Ghats — 312 samples)                │
│                    --> Test on Region B (Northeast Himalayas — 264 samples)      │
│   Experiment TR-2: Train on Region B (Northeast Himalayas — 264 samples)        │
│                    --> Test on Region A (Western Ghats — 312 samples)            │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Explicit Sample Counts per Spatial Fold

#### Level 1: Within-Region Folds (Region A — Western Ghats)
- **Fold A1 (Test: Wayanad)**:
  - Training Set: Idukki ($51\text{ pos} + 153\text{ bkg}$) $+$ Kodagu ($9\text{ pos} + 27\text{ bkg}$) $= \mathbf{240\text{ samples}}$ ($60\text{ pos}, 180\text{ bkg}$).
  - Test Set: Wayanad $= \mathbf{72\text{ samples}}$ ($18\text{ pos}, 54\text{ bkg}$).
- **Fold A2 (Test: Idukki)**:
  - Training Set: Wayanad ($18\text{ pos} + 54\text{ bkg}$) $+$ Kodagu ($9\text{ pos} + 27\text{ bkg}$) $= \mathbf{108\text{ samples}}$ ($27\text{ pos}, 81\text{ bkg}$).
  - Test Set: Idukki $= \mathbf{204\text{ samples}}$ ($51\text{ pos}, 153\text{ bkg}$).
- **Fold A3 (Test: Kodagu)**:
  - Training Set: Wayanad ($18\text{ pos} + 54\text{ bkg}$) $+$ Idukki ($51\text{ pos} + 153\text{ bkg}$) $= \mathbf{276\text{ samples}}$ ($69\text{ pos}, 207\text{ bkg})$.
  - Test Set: Kodagu $= \mathbf{36\text{ samples}}$ ($9\text{ pos}, 27\text{ bkg}$).

#### Level 1: Within-Region Folds (Region B — Northeast)
- **Fold B1 (Test: East Sikkim)**:
  - Training Set: West Sikkim ($13\text{ pos} + 55\text{ bkg}$) $+$ East Khasi Hills ($21\text{ pos} + 115\text{ bkg}$) $= \mathbf{204\text{ samples}}$ ($34\text{ pos}, 170\text{ bkg}$).
  - Test Set: East Sikkim $= \mathbf{60\text{ samples}}$ ($32\text{ pos}, 28\text{ bkg}$).
- **Fold B2 (Test: West Sikkim)**:
  - Training Set: East Sikkim ($32\text{ pos} + 28\text{ bkg}$) $+$ East Khasi Hills ($21\text{ pos} + 115\text{ bkg}$) $= \mathbf{196\text{ samples}}$ ($53\text{ pos}, 143\text{ bkg beggar}$).
  - Test Set: West Sikkim $= \mathbf{68\text{ samples}}$ ($13\text{ pos}, 55\text{ bkg}$).
- **Fold B3 (Test: East Khasi Hills)**:
  - Training Set: East Sikkim ($32\text{ pos} + 28\text{ bkg}$) $+$ West Sikkim ($13\text{ pos} + 55\text{ bkg}$) $= \mathbf{128\text{ samples}}$ ($45\text{ pos}, 83\text{ bkg}$).
  - Test Set: East Khasi Hills $= \mathbf{136\text{ samples}}$ ($21\text{ pos}, 115\text{ bkg}$).

#### Level 2: Cross-Region Transfer
- **Experiment TR-1**: Train strictly on **Region A (312 samples)**; Evaluate on **Region B (264 samples)**.
- **Experiment TR-2**: Train strictly on **Region B (264 samples)**; Evaluate on **Region A (312 samples)**.

### 2.3 Group Inheritance
Background samples inherit the exact spatial group (district) of the polygon from which they were sampled. When Wayanad is the test set, **all Wayanad positives AND all Wayanad background samples are held out together**. No sample within Wayanad's geographic boundary is ever seen during training in Fold A1.

---

## 3. Strict Data Leakage Prevention & Inner Validation Feasibility

### 3.1 Inner Validation Feasibility Analysis

In a Leave-One-District-Out outer cross-validation setup with 3 districts per region, **holding out 1 test district leaves exactly 2 districts in the outer training fold**.

> [!WARNING]
> **Inner Cross-Validation Feasibility Audit**
> A "3-fold district-level inner spatial cross-validation" is **mathematically impossible** on 2 training districts. Attempting to force a 3-fold split across 2 districts would fail or cause invalid partitions.

To prevent test-fold leakage and maintain strict spatial independence, Phase 3 implements a **clearly documented 2-fold Leave-One-District-Out Inner CV**:

```
INNER VALIDATION ARCHITECTURE (Training on 2 Districts: D_train1 and D_train2)
┌────────────────────────────────────────────────────────────────────────┐
│ Outer Training Set = D_train1 + D_train2                               │
│                                                                        │
│   Inner Fold 1:                                                        │
│     Inner Train = D_train1  ──────────> Inner Val = D_train2          │
│                                                                        │
│   Inner Fold 2:                                                        │
│     Inner Train = D_train2  ──────────> Inner Val = D_train1          │
│                                                                        │
│   Objective: Select hyperparameter configuration minimizing average    │
│              inner validation log-loss / maximizing inner PR-AUC.      │
└────────────────────────────────────────────────────────────────────────┘
```

- **Alternative Inner Partition (Spatial Coordinate Clustering)**:
  If an inner fold requires further regularization (e.g. when one training district has disproportionate sample counts, such as Idukki with 204 samples vs. Kodagu with 36 samples in Fold A1), the training set coordinates $(\text{lat}, \text{lon})$ are partitioned into $K=2$ spatial clusters via spatial KMeans fitted on **training coordinates only**.
- **Zero Test-Fold Leakage**: Under both options, **zero samples from the held-out test district are ever touched** during inner validation, scaling, hyperparameter tuning, or threshold selection.

### 3.2 End-to-End Leakage-Free Pipeline Flow

```
                             TRAINING PIPELINE (OUTER FOLD k)
┌────────────────────────────────────────────────────────────────────────┐
│  Outer Training Data (2 Train Districts Only)                          │
│       │                                                                │
│       ├──> Preprocessing: Fit StandardScaler on Outer Train Only       │
│       │                                                                │
│       ├──> Hyperparameter Tuning: 2-Fold Inner Spatial CV on Train     │
│       │    (Evaluates C for LogReg, max_depth/min_samples_leaf for RF) │
│       │                                                                │
│       ├──> Model Training: Fit Model on Full Outer Train Data          │
│       │                                                                │
│       └──> Threshold Optimization: Select tau* on Outer Train Only     │
│            (Maximize F1 subject to Target Recall >= 80% on Train)      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ FROZEN PARAMETERS & THRESHOLD ONLY
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  HELD-OUT TEST DISTRICT (Unseen Test Data)                             │
│       │                                                                │
│       ├──> Transform using FROZEN StandardScaler                       │
│       ├──> Predict probabilities using FROZEN Model                    │
│       ├──> Apply FROZEN tau* threshold                                 │
│       └──> Calculate Test Metrics (PR-AUC, ROC-AUC, Nominal P, R, F1)  │
│            (If Test Recall < 80%, report actual recall honestly)       │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Preprocessing & Feature Scaling**:
   - `StandardScaler` parameters ($\mu_{\text{train}}, \sigma_{\text{train}}$) are computed strictly on the training fold.
   - The fitted transformer is applied frozen to the held-out test fold. The test fold's mean and variance are never computed.
2. **Feature Selection (if applied)**:
   - Any variance-threshold or collinearity filtering is fitted strictly on the training fold.
3. **Hyperparameter Tuning**:
   - Tuned strictly inside the 2-fold inner spatial CV loop on training data.
4. **Decision Threshold Selection ($\tau^*$)**:
   - Selected strictly on training fold out-of-fold or training predictions.

---

## 4. Baseline Model Specifications & Identical Fold Comparisons

To guarantee a fair, scientifically sound comparison, **Logistic Regression and Random Forest are evaluated on the exact same outer spatial folds across all three feature sets**.

### 4.1 Model Architectures & Hyperparameter Spaces

| Architecture | Model Family | Inductive Bias & Strengths | Hyperparameter Grid (Inner CV) | Viva Justification |
|---|---|---|---|---|
| **Model 1: Logistic Regression** | Linear / Generalized Linear Model | Assumes monotonic log-odds; produces transparent coefficients and Odds Ratios ($e^{\beta_i}$). High regularization resistance to overfitting. | Penalty: L2 (`Ridge`), $C \in [0.01, 0.1, 1.0, 10.0]$, `solver='lbfgs'`, `class_weight='balanced'`. | Establishes the simplest linear baseline. If a complex non-linear ensemble cannot beat regularized logistic regression on spatial CV, tree complexity is unjustified. |
| **Model 2: Random Forest** | Non-Linear Tree Ensemble | Captures non-linear terrain-rainfall threshold interactions (e.g. slope $\ge 28^\circ$ AND $R_{15\text{d}} \ge 200\text{ mm}$); resistant to feature collinearity and outliers. | `n_estimators`: $[100, 200]$, `max_depth`: $[4, 6]$, `min_samples_leaf`: $[3, 5]$, `class_weight`: `'balanced_subsample'`, `random_state`: 42. | Provides robust ensemble capability with natural tree-based SHAP explainability. Kept shallow (`max_depth <= 6`) to prevent memorization of training terrain. |

### 4.2 Three Feature Set Benchmarks

To empirically answer: *Do multi-scale zonal terrain features outperform naive single-pixel features under 5–10 km positional uncertainty?*, each model will be evaluated across three structured feature subsets:

1. **Feature Set 1: Baseline Point Features Only** (5 features):
   - `elevation_m`, `slope_deg`, `rain_3d_mm`, `rain_7d_mm`, `rain_15d_mm`
2. **Feature Set 2: Multi-Scale Zonal Terrain + Point Rainfall** (14 features):
   - Multi-scale slope and relief (`slope_max`, `slope_p90`, `elev_relief` across 1 km, 3 km, 5 km) $+$ `rain_3d_mm`, `rain_7d_mm`, `rain_15d_mm` $+$ point elevation and slope.
3. **Feature Set 3: Full Feature Set (Zonal Terrain + 3 km Areal Mean Rainfall)** (17 features):
   - All Feature Set 2 features $+$ `rain_3km_mean_3d`, `rain_3km_mean_7d`, `rain_3km_mean_15d`.

### 4.3 Rigorous Comparison Matrix

- **Identical Folds**: Folds A1, A2, A3, B1, B2, B3, TR-1, TR-2 contain the exact same sample IDs and spatial boundaries across Model 1 and Model 2, and across Feature Sets 1, 2, and 3.
- **Fitting Rule**: All preprocessing, scaling, hyperparameter tuning, and threshold selection are re-fitted strictly on training fold data for each combination independently.

---

## 5. Threshold Selection Protocol & Target Recall Handling

In presence-unlabeled problems with $1:3$ imbalance, the default $0.50$ probability threshold is arbitrary. An operational decision threshold $\tau^*$ must be chosen systematically.

### 5.1 Training-Only Optimization Procedure

1. **Threshold Sweep**:
   - The threshold search evaluates candidate thresholds $\tau \in [0.05, 0.95]$ in increments of $\Delta \tau = 0.01$ using **training data only**.
2. **Target Recall Constraint**:
   - The optimization seeks $\tau^*$ that maximizes the training F1-score subject to satisfying an operational recall target:
     $$\tau^* = \arg\max_{\tau} \left\{ \text{F1}_{\text{train}}(\tau) \;\middle|\; \text{Recall}_{\text{train}}(\tau) \ge 80.0\% \right\}$$
3. **Freezing the Threshold**:
   - Once selected on the training fold, $\tau^*$ is **frozen**. It is evaluated exactly once on the held-out test fold. Test-fold labels are never used to tune or adjust $\tau^*$.

### 5.2 Strict Policy for Target Recall Deficits (Truth in Reporting)

Under spatial cross-validation, regional environmental differences (covariate shift) can make meeting an $80\%$ recall target challenging.

> [!IMPORTANT]
> **Mandatory Policy on Unmet Targets**
> - **Training Deficit**: If no threshold on the training fold achieves $\text{Recall}_{\text{train}} \ge 80.0\%$ (e.g. if the maximum achievable recall on training data is $74\%$), the pipeline selects the threshold yielding the highest achievable recall, records the achieved value, flags `target_recall_met_train = False`, and documents the specific limitation in the experimental report.
> - **Test Deficit**: If the frozen threshold $\tau^*$ achieves $< 80.0\%$ recall on the held-out test fold (e.g., $68.5\%$), the report **must report the actual achieved test recall plainly**.
> - **Never Claim Compliance When Unmet**: Under no circumstances will a fold be reported as "meeting the target" or "achieving operational safety" if the empirical recall falls below $80.0\%$. The limitation will be explicitly analyzed as a consequence of spatial domain shift between districts.

---

## 6. Presence-Unlabeled (PU) Evaluation & Spatial Uncertainty

### 6.1 PU Metric Interpretation Boundaries

In historical landslide inventories, verified negative locations do not exist. Background samples represent **unlabeled landscape locations ($s = 0$)**, not confirmed non-landslides ($y = 0$).

Therefore, model evaluation metrics must be interpreted with strict scientific precision:

```
METRIC INTERPRETATION BOUNDARIES (VIVA DEFENSE MANDATE):

Metric                Definition in Phase 3                               Interpretation & Policy Boundary
---------------------------------------------------------------------------------------------------------------------------------
PR-AUC                Area under Precision-Recall curve against           PRIMARY Metric: Reflects model ranking of historical
                      sampled background labels (s in {0, 1}).             events against the 5 km-separated background pool.
ROC-AUC               Area under ROC curve against sampled                PRIMARY Metric: Probability that a documented event
                      background labels (s in {0, 1}).                     receives a higher score than a background point.
Recall (Sensitivity)  Fraction of documented historical landslides        CRITICAL Safety Metric: Measures detection of known
                      detected at frozen threshold tau*.                  historical landslides (target: >= 80%).
Nominal Precision     TP / (TP + FP) computed strictly against            NOMINAL PSEUDO-METRIC: Computed against sampled
                      sampled background points.                          background. DO NOT claim real-world precision is
                                                                          higher or lower.
Nominal F1-Score      Harmonic mean of Recall and Nominal Precision.      NOMINAL PSEUDO-METRIC: Report at frozen threshold tau*.
Accuracy              (TP + TN) / Total.                                  DISCARDED: Misleading on imbalanced PU datasets.
```

> [!CAUTION]
> **No Claims of Real-World Occurrence Performance**
> - All reported precision, PR-AUC, and F1 scores are **nominal metrics evaluated strictly against the sampled background distribution**.
> - **We do not claim that real-world precision is necessarily higher or lower**: Real-world precision depends on the unknown true prevalence of landslides across the unobserved landscape, reporting catalog completeness, and false-alarm rates in untracked areas.
> - These metrics **must not be presented as verified real-world occurrence-prediction performance**. They quantify discrimination between documented historical landslide events and 5 km-buffered background locations.

### 6.2 Uncertainty Estimation Respecting Spatial Grouping

#### Non-Independence of Spatial Samples
Standard bootstrap resampling randomly samples individual rows with replacement. This assumes observations are independent and identically distributed (i.i.d.).
In geospatial data, **spatial autocorrelation violates sample independence**. Points in the same valley or storm cell share unmeasured covariates (geology, rainfall system). Point-level i.i.d. bootstrap artificially shrinks standard errors, underestimating uncertainty.

#### Adopted Uncertainty Architecture
1. **Primary Uncertainty Measure (Empirical Spatial Fold Variance)**:
   - The primary and most defensible measure of performance uncertainty is the **empirical variation across the independent outer spatial folds** (mean, standard deviation, minimum, and maximum across Folds A1–A3 and B1–B3).
2. **Spatial Block / Cluster Bootstrap**:
   - Where resampling confidence intervals are computed, the sampling unit is a **spatial cluster / block** (resampling spatial units or sub-district clusters with replacement, rather than individual points).
3. **Explicit Documentation of Statistical Limitations**:
   - Because each geographic region contains only 3 districts (3 spatial holdouts per region), the number of independent macroscopic spatial units is inherently small ($N_{\text{districts}} = 3$).
   - This limitation will be documented in the viva presentation: asymptotic confidence intervals on small numbers of spatial clusters are approximate and should be viewed as illustrative bounds rather than exact parametric intervals.

---

## 7. SHAP (SHapley Additive exPlanations) Protocol

SHAP provides mathematically grounded local and global feature attribution based on cooperative game theory.

```
SHAP ATTRIBUTION VS. CAUSAL EXPLANATION:

What SHAP Model Attribution IS:                      What SHAP IS NOT (Causal Boundaries):
[✓] Quantifies each feature's marginal mathematical  [✗] Does NOT prove physical geotechnical causation.
    contribution to the model's output log-odds.     [✗] Does NOT establish that rainfall caused a slide
[✓] Shows directional impact in the training data        independent of unmodeled geotechnical factors
    (e.g. +0.35 log-odds for rain_15d > 250 mm).         (e.g. shear strength, soil depth, pore pressure).
[✓] Explains why the model assigned a high score     [✗] Does NOT overcome catalog bias (if events were
    to a specific historical disaster event.             reported along roads, SHAP reflects that bias).
```

### 7.1 Reference Distribution & Explainer Setup

1. **Training Background Data Only**:
   - To avoid data leakage and adhere to explainability standards, SHAP reference distributions are computed strictly using **training-fold background samples** (`X_train[y_train == 0]`).
   - For Random Forest, `shap.TreeExplainer` is used with the tree-path background distribution.
   - For Logistic Regression, `shap.LinearExplainer` is used with the training-fold background data.
2. **Attribution vs. Causation Viva Distinction**:
   - A high positive SHAP value for `slope_p90_3km` or `rain_15d_mm` means the model utilized these features to increase its relative susceptibility score.
   - It does **not** prove that 15-day rainfall was the physical trigger, nor does it account for unmeasured hydrologic processes (e.g. antecedent soil moisture saturation, pore-water pressure dissipation, fractured bedrock channels).
   - In the viva defense, SHAP will be presented as **model diagnostic attribution**, verifying that the model relies on physically reasonable hazard drivers rather than spatial artifacts.

---

## 8. Reproducibility Architecture & Record Keeping Manifest

To ensure complete transparency and enable replication during viva examination, all Phase 3 modeling experiments will produce structured, versioned artifacts:

### 8.1 Experiment Tracking Schema

Every experiment run will log the following manifest fields to [`reports/phase3_experiment_results.json`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/reports/phase3_experiment_results.json) and generate an audited markdown summary [`reports/phase3_model_evaluation_report.md`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/reports/phase3_model_evaluation_report.md):

```json
{
  "experiment_id": "EXP-Phase3-A1-RF-FS3",
  "timestamp": "2026-10-XXTXX:XX:XX",
  "random_seed": 42,
  "model_family": "RandomForestClassifier",
  "feature_set": "FeatureSet3_Full_17features",
  "outer_fold": "Fold_A1",
  "test_district": "Wayanad",
  "train_districts": ["Idukki", "Kodagu"],
  "sample_counts": {
    "train_pos": 60, "train_bkg": 180, "train_total": 240,
    "test_pos": 18, "test_bkg": 54, "test_total": 72
  },
  "inner_cv_method": "2-Fold Leave-One-District-Out",
  "selected_hyperparameters": {
    "max_depth": 4,
    "min_samples_leaf": 3,
    "n_estimators": 100
  },
  "threshold_optimization": {
    "tau_star": 0.32,
    "target_recall_threshold": 0.80,
    "training_recall_achieved": 0.833,
    "target_recall_met_train": true
  },
  "test_metrics": {
    "pr_auc": 0.000,
    "roc_auc": 0.000,
    "nominal_precision": 0.000,
    "test_recall": 0.000,
    "target_recall_met_test": true,
    "nominal_f1": 0.000,
    "brier_score": 0.000
  }
}
```

### 8.2 Reproducibility Checklist
- **Fixed Global Seed**: `seed = 42` for all NumPy, Scikit-Learn, and cross-validation procedures.
- **Model Checkpoints**: Fitted model objects and frozen scalers will be saved to `models/checkpoints/` using standard Scikit-Learn joblib serialization.
- **Code Modularity**: All training, spatial CV splitting, and evaluation logic will be implemented as clean, readable, well-commented Python modules under `src/models/`.

---

## 9. Operational Disclaimers & Advisory Boundaries

In adherence to AGENTS.md, all experimental reporting, dashboards, and viva presentations must prominently include the following three explicit boundaries:

1. **Relative Susceptibility, Not Calibrated Probability**:
   - The system outputs a **Relative Landslide Susceptibility Index (RLSI)**, ranking terrain and rainfall combinations from lowest to highest hazard.
   - It is **not** an operationally calibrated probability (e.g. a score of 0.85 means high relative susceptibility relative to background, not an 85% probability that a hill will collapse today).
2. **Not an Imminent Predictor**:
   - The model evaluates susceptibility under event-associated monsoon meteorological envelopes. It does not predict the exact day or hour of slope collapse.
3. **Advisory Decision Support Only**:
   - All outputs are research prototypes developed under CSE326/CSE276 and cannot replace official geotechnical surveys or IMD/GSI evacuation directives.

---

## 10. Summary Checklist & Phase 3 Status

- [x] **Dataset v1 Audited**: Verified 0 global 5 km positive violations, 0 global 3 km background violations, 100% polygon containment, 144 unique positive IDs, 0 nulls across 576 rows.
- [x] **Background Sampler Hardened**: Enforces global positive-event exclusion and global inter-background spacing across all district borders.
- [x] **Spatial Cross-Validation Formalized**: Two-tier architecture (Level 1: Within-Region Leave-One-District-Out; Level 2: Cross-Region Transfer).
- [x] **Inner Validation Feasibility Resolved**: Addressed 2-district training constraint via 2-fold Leave-One-District-Out inner CV and spatial coordinate clustering; zero test-fold leakage.
- [x] **Threshold Selection Protocol Clarified**: Optimized on training data only; explicit policy to report actual recall and document limitations if 80% target is unmet; no false claims of compliance.
- [x] **Spatial Uncertainty Formulated**: Acknowledged spatial autocorrelation and non-independence; empirical fold-to-fold variation prioritized; spatial block bootstrap specified with documented sampling unit limitations.
- [x] **PU Metric Interpretation Defined**: Metrics reported strictly against sampled background; no speculative claims that real-world precision is higher or lower; not presented as verified real-world occurrence performance.
- [x] **Identical Folds for Model & Feature Comparison**: Enforced 1:1 identical folds for Logistic Regression and Random Forest across Feature Sets 1, 2, and 3; all fitting restricted to training folds.
- [x] **SHAP Explainer Protocol Designed**: Training background reference distribution; explicit demarcation between mathematical model attribution and physical geotechnical causation.
- [x] **Reproducibility Manifest Specified**: Fixed seed 42, structured JSON logging, checkpoint serialization, and modular code layout.
- [x] **All Existing Files Preserved**: No models trained yet; awaiting user review.
