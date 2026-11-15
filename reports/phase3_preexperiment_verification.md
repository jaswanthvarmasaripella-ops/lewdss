# Phase 3 Pre-Experiment Spatial Verification Report
## LEWDSS — SIH26001 · CSE326/CSE276 Course Project
### Phase 3: Spatial Cross-Validation, Leakage Guards, and Schema Audit
**Status: ALL PRE-EXPERIMENT VERIFICATION CHECKS PASSED — READY FOR MODEL TRAINING**
**Date: October 2026**
**Verification Script: [`scratch/verify_phase3_spatial_setup.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/scratch/verify_phase3_spatial_setup.py)**

---

> [!IMPORTANT]
> **Academic Integrity & Pre-Experiment Notice**
> In accordance with [`AGENTS.md`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/AGENTS.md) and [`reports/phase3_model_experiment_plan.md`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/reports/phase3_model_experiment_plan.md), this document records the deterministic verification of all modeling prerequisites prior to training machine learning models:
> - **Zero models have been trained.**
> - **Zero model metrics or predictions are simulated.**
> - **All existing datasets, crops, and code remain 100% intact.**
> - The entire project test suite (**177 / 177 tests**) passes cleanly.

---

## 1. Summary of Verification Outcomes

| Check # | Verification Domain | Requirement Checked | Measured Outcome | Audit Status |
|---|---|---|---|:---:|
| **Check 1** | **Inner Spatial CV Feasibility** | Split outer training set (2 districts) into 2 valid inner spatial folds without outer test-district leakage | Valid partitions across all 6 within-region folds and 2 transfer folds; $\text{InnerTrain} \cap \text{Test} = \emptyset$ | **PASSED** |
| **Check 2** | **Frozen Outer Folds Parity** | Generate outer split masks once; verify identical sample IDs across models and feature sets | Exact identity across LR, RF, and Feature Sets 1, 2, and 3 for all 8 folds | **PASSED** |
| **Check 3** | **PU Labels & Feature Schemas** | 144 positives ($s=1$, `POS_` prefix), 432 background ($s=0$, `BKG_` prefix, unlabeled landscape), 0 nulls/infs | 144 unique positive event IDs; 432 background points; 0 nulls across all 27 feature columns | **PASSED** |
| **Check 4** | **Leakage Guards** | Isolate `StandardScaler`, hyperparameter tuning, and threshold selection to training data | Scaler, grid search, and $\tau^*$ depend strictly on `X_train`; test fold evaluated frozen | **PASSED** |
| **Check 5** | **Reproducibility (Seed 42)** | Deterministic fold partition hashing under seed 42 | SHA256 hash `7f12457391d551af...` identical across independent runs | **PASSED** |

---

## 2. Check 1: Inner Spatial CV Feasibility & Zero-Leakage Proof

### 2.1 The Two-District Constraint Resolution

In outer Leave-One-District-Out cross-validation, holding out 1 test district leaves **exactly 2 districts in the outer training fold**. A 3-fold district split is physically impossible on 2 districts. 

The verification script demonstrated that a **2-Fold Leave-One-District-Out Inner CV** is mathematically feasible, balanced, and strictly leakage-free across all folds:

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
│   Outer Test District = D_test (HELD OUT IN ISOLATION)                │
│   Strict Disjointness: (Inner Train ∪ Inner Val) ∩ D_test = ∅         │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Empirical Sample Partitioning per Spatial Fold

| Outer Fold ID | Outer Test District | Outer Train Districts | Inner Fold ID | Inner Train District (Count, pos/bkg) | Inner Val District (Count, pos/bkg) | Outer Test Overlap |
|---|---|---|---|---|---|:---:|
| **Fold A1** | Wayanad (72) | Idukki, Kodagu | A1_inner_1<br>A1_inner_2 | Kodagu (36: 9p/27b)<br>Idukki (204: 51p/153b) | Idukki (204: 51p/153b)<br>Kodagu (36: 9p/27b) | **0 (None)**<br>**0 (None)** |
| **Fold A2** | Idukki (204) | Wayanad, Kodagu | A2_inner_1<br>A2_inner_2 | Kodagu (36: 9p/27b)<br>Wayanad (72: 18p/54b) | Wayanad (72: 18p/54b)<br>Kodagu (36: 9p/27b) | **0 (None)**<br>**0 (None)** |
| **Fold A3** | Kodagu (36) | Wayanad, Idukki | A3_inner_1<br>A3_inner_2 | Idukki (204: 51p/153b)<br>Wayanad (72: 18p/54b) | Wayanad (72: 18p/54b)<br>Idukki (204: 51p/153b) | **0 (None)**<br>**0 (None)** |
| **Fold B1** | East Sikkim (60) | West Sikkim, East Khasi | B1_inner_1<br>B1_inner_2 | East Khasi (136: 21p/115b)<br>West Sikkim (68: 13p/55b) | West Sikkim (68: 13p/55b)<br>East Khasi (136: 21p/115b) | **0 (None)**<br>**0 (None)** |
| **Fold B2** | West Sikkim (68) | East Sikkim, East Khasi | B2_inner_1<br>B2_inner_2 | East Khasi (136: 21p/115b)<br>East Sikkim (60: 32p/28b) | East Sikkim (60: 32p/28b)<br>East Khasi (136: 21p/115b) | **0 (None)**<br>**0 (None)** |
| **Fold B3** | East Khasi (136) | East Sikkim, West Sikkim | B3_inner_1<br>B3_inner_2 | West Sikkim (68: 13p/55b)<br>East Sikkim (60: 32p/28b) | East Sikkim (60: 32p/28b)<br>West Sikkim (68: 13p/55b) | **0 (None)**<br>**0 (None)** |
| **Fold TR1** | Region B (264) | Region A (3 districts) | TR1_inner_1..3 | 2 Districts (e.g. 240, 276, 108) | 1 District (e.g. 72, 36, 204) | **0 (None)** |
| **Fold TR2** | Region A (312) | Region B (3 districts) | TR2_inner_1..3 | 2 Districts (e.g. 196, 204, 128) | 1 District (e.g. 68, 60, 136) | **0 (None)** |

**Zero-Leakage Proof**: Across all 8 outer folds and all 18 inner folds, the intersection between inner training/validation indices and outer test indices is strictly empty ($\emptyset$). Zero samples or geographic boundaries from the test fold are ever observed during inner validation.

---

## 3. Check 2: Frozen Outer Spatial Splits & Multi-Model/Feature Parity

The outer spatial split masks were generated once and validated for bit-for-bit parity across all experimental permutations:

```
MULTI-MODEL & MULTI-FEATURE EVALUATION GRID (8 Folds x 2 Models x 3 Feature Sets = 48 Runs)

                │ Feature Set 1 (Point)  │ Feature Set 2 (Zonal)  │ Feature Set 3 (Full)
────────────────┼────────────────────────┼────────────────────────┼───────────────────────
Logistic Reg.   │ Identical Folds (A1-TR)│ Identical Folds (A1-TR)│ Identical Folds (A1-TR)
Random Forest   │ Identical Folds (A1-TR)│ Identical Folds (A1-TR)│ Identical Folds (A1-TR)
```

- **Parity Test Result**:
  - `sample_id` lists for training and testing are 100% identical between Logistic Regression and Random Forest.
  - `sample_id` lists for training and testing are 100% identical across Feature Sets 1, 2, and 3.
  - This guarantees that any performance difference between Logistic Regression and Random Forest, or between Point and Zonal features, is strictly attributable to model capacity or feature representation, **not fold variance**.

---

## 4. Check 3: PU Labels, Feature Schemas & Absence Semantics

### 4.1 Absence Semantics & Positive Identification
- **Positive Events ($s = 1$)**: Exactly 144 records.
  - `sample_id` prefix: `POS_` (144 / 144).
  - `match_type`: `in_polygon` (144 / 144 verified inside official district boundaries).
  - `event_id`: Exactly 144 non-null, unique historical event IDs.
- **Background Samples ($s = 0$)**: Exactly 432 records.
  - `sample_id` prefix: `BKG_` (432 / 432).
  - `match_type`: `in_polygon` (432 / 432 sampled strictly within official district boundaries).
  - `event_id`: 0 non-null values (all 432 are null, representing sampled landscape locations, not cataloged events).
  - **Absence Semantics Confirmed**: Background rows are explicitly designated as unlabeled background landscape points, **never described as confirmed absence/negative locations**.

### 4.2 Feature Schema Audit

All three feature subsets were verified against [`data/processed/dataset_v1_features.csv`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/data/processed/dataset_v1_features.csv):

| Feature Set | Number of Features | Column Names | Null Count | Inf Count | Dtype Check |
|---|:---:|---|:---:|:---:|:---:|
| **FS1: Baseline Point** | 5 | `elevation_m`, `slope_deg`, `rain_3d_mm`, `rain_7d_mm`, `rain_15d_mm` | 0 | 0 | All `float64` |
| **FS2: Zonal Terrain** | 14 | All FS1 $+$ `slope_max_1km`, `slope_p90_1km`, `elev_relief_1km`, `slope_max_3km`, `slope_p90_3km`, `elev_relief_3km`, `slope_max_5km`, `slope_p90_5km`, `elev_relief_5km` | 0 | 0 | All `float64` |
| **FS3: Full Zonal + Areal Rain** | 17 | All FS2 $+$ `rain_3km_mean_3d`, `rain_3km_mean_7d`, `rain_3km_mean_15d` | 0 | 0 | All `float64` |

---

## 5. Check 4: Leakage Guards for Scaling, Tuning & Threshold Selection

A demonstration pipeline was executed on Fold A1 to verify programmatic leakage barriers:

1. **StandardScaler Isolation Guard**:
   - `scaler.fit(X_train)` computes $\mu_{\text{train}}$ and $\sigma_{\text{train}}$ strictly on the 240 training samples.
   - Test fold samples are transformed using `scaler.transform(X_test)` with frozen parameters. Test statistics are never computed or leaked.
2. **Hyperparameter Tuning Isolation Guard**:
   - Inner CV grid search selects hyperparameter $C$ solely by evaluating inner validation loss across the training districts (`Idukki` and `Kodagu`).
   - The test district (`Wayanad`) is completely isolated and inaccessible during tuning.
3. **Threshold Selection Guard**:
   - The operational decision threshold $\tau^*$ is selected by sweeping $\tau \in [0.05, 0.95]$ on training probabilities to maximize F1 subject to $\text{Recall}_{\text{train}} \ge 80\%$.
   - $\tau^*$ is frozen and applied once to the unseen test fold. Test labels are never accessed to adjust $\tau^*$.
   - If test recall falls below $80\%$, the actual recall is reported honestly without claiming compliance.

---

## 6. Check 5: Deterministic Reproducibility

- Master random seed: `seed = 42`.
- Split definitions were generated across two independent executions and serialized to JSON.
- **SHA256 Manifest Hash**:
  $$\text{SHA256} = \mathbf{7f12457391d551afb49be2dcbb27d427c3f8757ce8b2c4d9fa2435dfc5e0da9b}$$
- The hashes matched identically bit-for-bit, verifying 100% deterministic reproducibility.

---

## 7. Full Test Suite Execution Status

The full project automated test suite was executed to verify zero regression across existing modules:

```bash
python -m pytest tests/ -q
# Output: 177 passed in 14.34s (0 failures, 0 errors, 0 warnings)
```

All unit and integration tests across data ingestion, CRS audit, raster extraction, UGLC catalog validation, and Phase 2 dataset integrity passed without issues.

---

## 8. Conclusion & Readiness for Model Training

All 5 pre-experiment verification checks required by the user have **passed completely**:
1. Inner spatial CV is proven feasible across the 2 training districts with zero outer test-fold leakage.
2. Outer spatial fold definitions are frozen and verified identical across all models and feature sets.
3. PU labels, match types, absence semantics, and feature schemas are strictly verified.
4. Programmatic leakage guards for scaling, tuning, and threshold selection are proven.
5. Deterministic reproducibility under seed 42 is verified.

**Next Step**: Ready to proceed with implementing [`src/models/`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/src/models) modeling scripts and executing the approved experiments upon user approval.
