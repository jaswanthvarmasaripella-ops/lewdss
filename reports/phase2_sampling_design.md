# Phase 2 Engineering & Methodological Design (Revised): Presence-Background Dataset, Multi-Scale Features, and Spatial Validation
## LEWDSS — SIH26001 · CSE326/CSE276 Course Project
### Phase 2: Comprehensive Design Specification for Dataset Construction and Feature Pipeline
**Status: REVISED DESIGN SPECIFICATION — AWAITING USER REVIEW PRIOR TO IMPLEMENTATION**
**Date: October 2026**

---

> [!IMPORTANT]
> **Advisory Scope & Academic Integrity Notice**
> This document specifies the revised architectural and experimental design for Phase 2.
> - **No background samples have been generated.**
> - **No machine learning models have been trained.**
> - **No existing datasets or baseline files have been modified or deleted.**
> - All empirical measurements reported herein reflect real, measured sensitivity tests and geographic area calculations performed on the active project repository.

---

## 1. Primary Positive-Event Inventory Specification

In strict accordance with [`AGENTS.md`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/AGENTS.md) and the findings of [`reports/baseline_attribution_review.md`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/reports/baseline_attribution_review.md), the primary positive-event inventory (`dataset_v1_positive`) is strictly restricted to verified in-polygon events.

### 1.1 Inventory Summary

- **Total Retained Positive Records**: **144**
- **Unique Event IDs**: **144** (100% unique; zero duplicate records)
- **Geographic Attribution**: Every event coordinate $(lon, lat)$ is verified to lie strictly inside the official administrative boundary polygon in [`data/raw/boundaries/target_districts.geojson`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/data/raw/boundaries/target_districts.geojson).
- **Temporal Span**: 2004 to 2022 (100% day-level date precision).
- **Data Completeness**:
  - Copernicus GLO-30 DEM (30m): **144 / 144 (100.0%)**
  - CHIRPS v2.0 Rainfall (0.05°): **144 / 144 (100.0%)**

### 1.2 District Breakdown & Tile Allocation

```
Region / District               Positive Count   Polygon Containment   DEM Tile Coverage
-----------------------------------------------------------------------------------------
Region A (Western Ghats):
  Wayanad (Kerala)                          18              100.0%             N11_E075, N11_E076
  Idukki (Kerala)                           51              100.0%             N09_E076, N09_E077, N10_E076, N10_E077
  Kodagu (Karnataka)                         9              100.0%             N11_E075, N11_E076, N12_E075, N12_E076
  Subtotal Region A                         78              100.0%             8 unique tiles

Region B (Northeast):
  East Sikkim                               32              100.0%             N27_E088
  West Sikkim                               13              100.0%             N27_E088
  East Khasi Hills (Meghalaya)              21              100.0%             N25_E091, N25_E092
  Subtotal Region B                         66              100.0%             3 unique tiles
-----------------------------------------------------------------------------------------
TOTAL                                      144              100.0%             11 unique tiles
```

### 1.3 Handling of Non-Polygon Records & Duplicate Provenance

1. **Duplicate ID 888497**: Physically located in Devikulam/Munnar, Idukki. Retained under **Idukki** (`in_polygon`). The duplicate Wayanad assignment (caused by keyword matching on newspaper text) is permanently removed from positive training data.
2. **Duplicate ID 888047**: Physically located in Aralam forest, Kannur district outside target polygons (`in_bbox`). Excluded from the primary in-polygon inventory; preserved in audit logs.
3. **Bounding-Box Only Records (67 events)**: Maintained in a separate evaluation table (`dataset_v1_bbox_corridor.csv`) for secondary sensitivity benchmarking of transport lifelines, but excluded from primary positive training labels.
4. **Text-Only Records (43 events)**: Formally excluded from all modeling and validation. Never treated as confirmed geographic events.

---

## 2. Temporal Matching & Dynamic Rainfall Attribution

### 2.1 Distinguishing Spatial Susceptibility from Time-Specific Occurrence

Landslide risk modeling combines two distinct components:
1. **Static Spatial Susceptibility**: Where landslides can occur based on fixed topography (elevation, slope, relief). This property does not vary day to day.
2. **Dynamic Triggering / Time-Specific Occurrence**: When landslides occur based on antecedent rainfall.

If background samples are assigned dates at random across the entire calendar year (e.g., dry winter months of December or January), the classifier trivially learns that landslides occur during summer rain and not winter dry periods. The model would degenerate into an ordinary "is it monsoon season?" detector rather than learning true slope-destabilizing precipitation thresholds.

### 2.2 Defensible Date-Assignment Protocol for Background Samples

To ensure dynamic rainfall features are scientifically comparable with positive events, background points receive temporal assignments using a **Monsoon-Constrained Historical Sampling Protocol**:

```
                       HISTORICAL MONSOON TEMPORAL WINDOW
                     [June 1 to September 30 across 2004–2022]
                                         │
        ┌────────────────────────────────┴────────────────────────────────┐
        ▼                                                                 ▼
[Strategy 1: Date-Paired Co-occurrence]          [Strategy 2: Stratified Monsoon Sampling]
Assign background points the exact date of       Randomly sample (year, month, day) from
a positive landslide in the same district.       June–Sept across 2004–2022, verifying
Answers: "On the day Wayanad slipped, what       unbroken 15-day CHIRPS raster coverage
was the rain in unfailed parts of the district?" on disk.
```

1. **Temporal Domain**: Restricted strictly to the active **south-west monsoon months (June 1 to September 30)** across the catalog operational window (**2004 to 2022**).
2. **Rainfall-Window Availability Gate**:
   - Before accepting any candidate date $t$, the pipeline verifies that all 15 daily CHIRPS regional crop TIFFs $\{t-14, \dots, t\}$ are present on disk.
   - If any single daily raster in the 15-day window is missing or contains corrupt/sentinel pixels at the coordinate, the candidate date is rejected and re-drawn.
3. **District/Region Synchrony**:
   - When using Date-Paired Co-occurrence, background dates are drawn from the historical event date set of that specific district or region, ensuring realistic regional meteorology.
4. **Scientific Defense for Viva**: By restricting the temporal background domain to monsoon days, the machine learning model is forced to evaluate: *"Given that it is currently monsoon season in the Western Ghats / Himalayas, what specific combination of 3-day, 7-day, and 15-day rainfall on this terrain triggers a failure versus safe drainage?"*

---

## 3. Empirical Sampling Feasibility & Capacity Audit

To test whether the target ratio of $1:3$ (432 background points) is physically achievable, an empirical Monte Carlo spatial capacity audit was executed across all six district polygons.

### 3.1 Spatial Constraints Enforced
1. **Polygon Boundary**: Point must fall strictly within the official district boundary polygon.
2. **Event Exclusion Buffer**: Point must be $\ge 5.0\text{ km}$ from all known historical landslide points in that district.
3. **Inter-Sample Distance**: Candidate points must maintain a minimum distance of $d_{\text{min}} = 3.0\text{ km}$ from all other background points. Under random spatial packing with irregular boundaries, each sample requires approximately $1.2 \times d_{\text{min}}^2 \approx 10.8\text{ km}^2$ of eligible terrain.

### 3.2 Measured District Sampling Capacity

| District | Total District Area | Positive Events | Area Excluded by 5 km Buffer | Remaining Eligible Area | Practical Capacity ($d \ge 3\text{ km}$) | Target Count (1:3 Ratio) | Feasible at 1:3? |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Kodagu** | $4,099.0\text{ km}^2$ | 9 | $395.0\text{ km}^2$ (9.6%) | $3,704.0\text{ km}^2$ | **342** | 27 | **YES** (12.7× capacity) |
| **Idukki** | $4,993.3\text{ km}^2$ | 51 | $2,084.6\text{ km}^2$ (41.7%) | $2,908.7\text{ km}^2$ | **269** | 153 | **YES** (1.8× capacity) |
| **Wayanad** | $2,124.6\text{ km}^2$ | 18 | $897.3\text{ km}^2$ (42.2%) | $1,227.3\text{ km}^2$ | **113** | 54 | **YES** (2.1× capacity) |
| **East Khasi Hills** | $2,837.5\text{ km}^2$ | 21 | $715.9\text{ km}^2$ (25.2%) | $2,121.6\text{ km}^2$ | **196** | 63 | **YES** (3.1× capacity) |
| **West Sikkim** | $1,160.4\text{ km}^2$ | 13 | $402.6\text{ km}^2$ (34.7%) | $757.8\text{ km}^2$ | **70** | 39 | **YES** (1.8× capacity) |
| **East Sikkim** | $940.7\text{ km}^2$ | 32 | **$622.9\text{ km}^2$ (66.2%)** | **$317.8\text{ km}^2$** | **29** | **96** | **NO (Capacity Deficit)** |
| **TOTAL** | **$16,155.5\text{ km}^2$** | **144** | **$5,118.3\text{ km}^2$ (31.7%)** | **$11,037.2\text{ km}^2$** | **1,019** | **432** | **YES (Globally / Regionally)** |

### 3.3 The East Sikkim Capacity Deficit & Resolution Strategy

**Critical Finding**: In East Sikkim, 32 historical landslides cluster heavily across a compact district of only $940.7\text{ km}^2$. Constructing $5\text{ km}$ exclusion discs around all 32 points eliminates **$66.2\%$** of the district's total geographic area. The remaining $317.8\text{ km}^2$ can physically accommodate at most **$\sim 29$ background points** before violating the $3.0\text{ km}$ spacing rule. Demanding 96 background points from East Sikkim would compress inter-sample spacing to $< 1.8\text{ km}$, causing severe spatial autocorrelation.

**Defensible Resolution Alternatives:**
- **Recommended Policy (Regional Quota Rebalancing)**:
  - Total Region B target background is $66 \times 3 = 198$ points.
  - The aggregate capacity of Region B is $29 + 70 + 196 = \mathbf{295\text{ points}}$ (well above the 198 target).
  - Allocate East Sikkim at its physical capacity of **28 points** ($\sim 1:1$ ratio).
  - Distribute the remaining 68 Region B points proportionally to West Sikkim ($55$ points, ratio $1:4.2$) and East Khasi Hills ($115$ points, ratio $1:5.5$).
  - This strictly respects physical terrain constraints while preserving the regional sample size and preventing artificial packing.
- **Alternative Policy (Adaptive Buffer in East Sikkim)**:
  - If a strict 1:3 ratio within East Sikkim is required, reduce East Sikkim's positive exclusion radius from $5.0\text{ km}$ to $3.0\text{ km}$ (which increases eligible area to $\sim 580\text{ km}^2$, supporting $\sim 55$ samples), and reduce spacing to $2.2\text{ km}$.
  - *Recommendation*: Use Regional Quota Rebalancing to maintain the $5\text{ km}$ exclusion integrity.

---

## 4. Multi-Scale Terrain Feature Engineering & Outlier Sensitivity

### 4.1 Zonal Buffer Extraction Specification

For each sample point (positive or background), the pipeline extracts terrain statistics across three concentric circular buffers: $R \in \{1\text{ km}, 3\text{ km}, 5\text{ km}\}$.

1. **Maximum Slope** ($\text{slope\_max}_R$): Peak gradient within the buffer.
2. **90th-Percentile Slope** ($\text{slope\_p90}_R$): Non-parametric upper-tail steepness.
3. **Elevation Relief** ($\text{elev\_relief}_R = \max \text{elev} - \min \text{elev}$): Topographic roughness and gravitational potential energy.
4. **Point Baseline Preserved**: Single-pixel `elevation_m` and `slope_deg` are retained for all records.

### 4.2 Outlier Sensitivity of Maximum Slope vs. Percentile Slope (Viva Defense)

| Metric | Mathematical Character | Vulnerability to DEM Artifacts | Physical Representation |
|---|---|---|---|
| **$\text{slope\_max}_R$** | Extreme-value statistic ($\max$) | **HIGH**. A single corrupted 30m pixel, cliff artifact, bridge embankment, or vertical gorge edge in a 5 km circle ($\sim 87,000$ pixels) drives the value to $65^\circ\text{--}75^\circ$. | Confirms whether extreme vertical relief exists anywhere within the uncertainty zone. |
| **$\text{slope\_p90}_R$** | Non-parametric quantile ($90\%$) | **ROBUST**. Immune to individual pixel spikes; reflects the genuine prevailing slope of the steepest decile of the surrounding terrain. | Primary gradient feature for tree-based modeling. |

### 4.3 Geodesic Distance Calculation & NoData Handling

1. **Geodesic Distances**:
   All buffer masks on Copernicus DEM tiles use exact latitude-corrected metric distances:
   $$\Delta x_{\text{meters}} = \Delta lon \times 111,320 \times \cos\left(\frac{lat_1 + lat_2}{2}\right)$$
   $$\Delta y_{\text{meters}} = \Delta lat \times 111,320$$
2. **NoData Handling in Rasters**:
   - Copernicus DEM tiles have zero missing pixels across land surfaces. Any boundary/void pixel ($\le -9000$) is excluded from buffer arrays prior to quantile computation.
   - If $> 20\%$ of pixels within a buffer are void (e.g. coastal edge), the record is flagged with `dem_partial = True`.

---

## 5. Measured CHIRPS Rainfall Sensitivity

Empirical coordinate perturbation tests across 24 stratified events (768 extractions) confirm the spatial sensitivity of CHIRPS accumulations:

```
Perturbation Distance      3-day Window (R_3d)      7-day Window (R_7d)     15-day Window (R_15d)
-------------------------------------------------------------------------------------------------
1.0 km Shift               3.55% (2.11 mm)          2.70% (2.91 mm)          1.60% (3.59 mm)
2.0 km Shift               9.04% (5.09 mm)          6.48% (7.31 mm)          4.54% (9.86 mm)
5.0 km Shift              17.73% (10.73 mm)        14.44% (16.28 mm)        10.45% (21.04 mm)
10.0 km Shift             26.55% (14.69 mm)        19.71% (23.53 mm)        16.89% (32.42 mm)
```

**Methodological Defense:**
- Sub-kilometer shifts ($\le 1\text{ km}$) exhibit negligible variation ($\le 3.55\%$).
- At the $5\text{ km}$ catalog uncertainty limit, mean variation is $10.5\%\text{--}17.7\%$.
- 15-day accumulations are nearly twice as stable as 3-day accumulations because multi-week integration dampens localized storm gradients.
- To provide robustness against cell-edge shifts, the pipeline will extract a **$3\text{ km}$ areal mean CHIRPS rainfall** alongside single-pixel rainfall.

---

## 6. Spatial Validation Strategy & Metric Interpretation

Standard random $k$-fold cross-validation is **rejected** because spatial autocorrelation between nearby points in training and validation folds produces artificial data leakage and false high accuracy.

### 6.1 Explicit Train/Test Assignments

```
SPATIAL VALIDATION ARCHITECTURE:

Level 1: Within-Region Spatial Group CV (Leave-One-District-Out)
┌──────────────────────────────────────────────────────────────────────────────────┐
│ REGION A (Western Ghats):                                                        │
│   Fold A1: Train on [Idukki + Kodagu]         --> Test on [Wayanad]              │
│   Fold A2: Train on [Wayanad + Kodagu]        --> Test on [Idukki]               │
│   Fold A3: Train on [Wayanad + Idukki]        --> Test on [Kodagu]               │
│                                                                                  │
│ REGION B (Northeast):                                                            │
│   Fold B1: Train on [West Sikkim + E. Khasi]  --> Test on [East Sikkim]          │
│   Fold B2: Train on [East Sikkim + E. Khasi]  --> Test on [West Sikkim]          │
│   Fold B3: Train on [East Sikkim + W. Sikkim] --> Test on [East Khasi Hills]     │
└──────────────────────────────────────────────────────────────────────────────────┘

Level 2: Cross-Region Transferability Benchmark (Domain Adaptation)
┌──────────────────────────────────────────────────────────────────────────────────┐
│   Experiment TR-1: Train on Region A (Western Ghats) --> Test on Region B (NE)   │
│   Experiment TR-2: Train on Region B (NE) --> Test on Region A (Western Ghats)   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Group Inheritance & Leakage Prevention
1. **Background Group Inheritance**: Background samples inherit the exact spatial group (district) of the polygon from which they were sampled.
2. **Strict Block Isolation**: When Wayanad is the test set, **all Wayanad positives AND all Wayanad background samples are held out simultaneously**. No sample within Wayanad's geographic boundary is visible to the training algorithm.

### 6.3 Threshold Tuning Without Test Leakage
1. **Training Set Optimization**: The classification decision threshold $\tau^*$ is determined strictly on the training fold using internal cross-validation (e.g. optimizing F1 at a target recall of $85\%$).
2. **Test Set Evaluation**: $\tau^*$ is frozen and applied once to the held-out test district. Test fold data is never inspected during threshold selection.

---

## 7. Presence-Unlabeled (PU) Limitations & Metric Semantics

### 7.1 Mathematical Foundation of PU Data

In historical disaster inventories, confirmed non-events do not exist. Background samples are **unlabeled ($s = 0$)**, not confirmed absences ($y = 0$).

Following the established PU learning literature (Ward et al., 2009; Elith et al., 2011), the observed sample indicator $s \in \{0, 1\}$ relates to the true latent state $y \in \{0, 1\}$ by:

$$P(s = 1 \mid \mathbf{x}) = c \cdot P(y = 1 \mid \mathbf{x})$$

where $c = P(s = 1 \mid y = 1)$ is the unknown catalog recording probability ($0 < c < 1$).

### 7.2 Consequences for Performance Metric Interpretation

1. **Model Scores Are Not Calibrated Probabilities**:
   - The model output represents an **Index of Relative Landslide Susceptibility (RLSI)**, ranking terrain from lowest to highest likelihood of failure relative to monsoon background conditions.
   - It must **NEVER** be called an absolute real-world probability.
2. **Accuracy is Uninformative**:
   - In a 1:3 imbalanced dataset, a dummy classifier predicting "no landslide" everywhere achieves $75\%$ accuracy while detecting 0 landslides. Accuracy is discarded.
3. **Nominal Precision & F1 Underestimate True Performance**:
   - Background samples in steep, wet terrain may be unrecorded historical landslides.
   - When the model predicts a high score for such points, standard evaluation marks them as "false positives", artificially deflating nominal precision.
4. **Primary Evaluation Metrics**:
   - **PR-AUC (Precision-Recall AUC)**: Evaluates trade-off across the minority positive class.
   - **ROC-AUC**: Evaluates relative ranking power (probability that a true landslide receives a higher score than a random background point).
   - **Per-District Recall**: Verifies whether catastrophic events in test districts are caught.

---

## 8. Reproducibility, Target Schema & Outputs

### 8.1 Configuration & Seeds
- Master Random Seed: **`seed: 42`** (governs coordinate generation, date sampling, and train/test splits).
- Configuration File: [`configs/config.yaml`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/configs/config.yaml).

### 8.2 Unified Dataset Schema (`data/processed/dataset_v1_features.csv`)

```
Field Name           Type        Units       Source      Description
---------------------------------------------------------------------------------------------------
sample_id            str         -           Pipeline    Unique ID (e.g., POS_888036, BKG_IDUKKI_001)
is_positive          int         {0, 1}      UGLC/PU     1 = Recorded Landslide; 0 = Unlabeled Background
event_id             str/null    -           UGLC        Original UGLC ID (null for background)
event_date           str (ISO)   YYYY-MM-DD  UGLC/Sample Event date or assigned monsoon date
lon                  float       degrees E   WGS84       Longitude coordinate
lat                  float       degrees N   WGS84       Latitude coordinate
district             str         -           GeoJSON     Target district name
region               str         -           Config      Region A (Western Ghats) or Region B (Northeast)
match_type           str         -           GeoJSON     in_polygon (strictly verified)

-- Baseline Point Features --
elevation_m          float       metres      DEM 30m     Terrain elevation at coordinate
slope_deg            float       degrees     DEM 30m     Horn's 3x3 slope at coordinate
rain_3d_mm           float       mm          CHIRPS      3-day cumulative rainfall ending on event_date
rain_7d_mm           float       mm          CHIRPS      7-day cumulative rainfall ending on event_date
rain_15d_mm          float       mm          CHIRPS      15-day cumulative rainfall ending on event_date

-- Multi-Scale DEM Zonal Features --
slope_max_1km        float       degrees     DEM 30m     Maximum slope within 1 km buffer
slope_p90_1km        float       degrees     DEM 30m     90th-percentile slope within 1 km buffer
elev_relief_1km      float       metres      DEM 30m     Elevation relief (max - min) within 1 km buffer
slope_max_3km        float       degrees     DEM 30m     Maximum slope within 3 km buffer
slope_p90_3km        float       degrees     DEM 30m     90th-percentile slope within 3 km buffer
elev_relief_3km      float       metres      DEM 30m     Elevation relief (max - min) within 3 km buffer
slope_max_5km        float       degrees     DEM 30m     Maximum slope within 5 km buffer
slope_p90_5km        float       degrees     DEM 30m     90th-percentile slope within 5 km buffer
elev_relief_5km      float       metres      DEM 30m     Elevation relief (max - min) within 5 km buffer

-- Areal Rainfall Feature --
rain_3km_mean_3d     float       mm          CHIRPS      3 km buffer mean 3-day rainfall
rain_3km_mean_7d     float       mm          CHIRPS      3 km buffer mean 7-day rainfall
rain_3km_mean_15d    float       mm          CHIRPS      3 km buffer mean 15-day rainfall

-- Quality & Verification Flags --
dem_available        bool        -           Pipeline    True if all DEM features extracted
rain_available       bool        -           Pipeline    True if all rainfall dates available
dem_partial          bool        -           Pipeline    True if coastal/border buffer intersected nodata
```

### 8.3 Exact Output Files (Post-Implementation)
- `data/processed/dataset_v1_features.csv` — Unified positive + background feature table.
- `data/processed/dataset_v1_bbox_corridor.csv` — Separate table of 67 bbox-only events for sensitivity testing.
- `data/processed/dataset_v1_metadata.json` — Provenance metadata, seed, sampling parameters, exclusion counts.
- `tests/test_phase2_dataset.py` — Automated tests verifying exclusion zones, zonal calculations, and date logic.
- `reports/phase2_dataset_verification_report.md` — Final validation report post-generation.

---

## 9. Explicit List of Unresolved Methodological Decisions

Before beginning implementation, the following decisions are explicitly documented for user confirmation:

1. **East Sikkim Capacity Resolution**:
   - *Option A (Recommended)*: Regional rebalancing (cap East Sikkim at 28 points, distribute remaining Region B background to West Sikkim and East Khasi Hills).
   - *Option B*: Relax East Sikkim positive exclusion buffer from $5.0\text{ km}$ to $3.0\text{ km}$ and spacing to $2.2\text{ km}$.
2. **Background Date Strategy**:
   - *Option A (Recommended)*: Date-Paired Co-occurrence (sample from the historical event date set of that district/region).
   - *Option B*: Uniform random draw of monsoon days (June 1 – September 30) across 2004–2022.
3. **Rainfall Buffer Feature**:
   - Include the $3\text{ km}$ areal mean CHIRPS rainfall in addition to point rainfall, or retain point rainfall only for simplicity during baseline modeling.

---

## 10. Summary Checklist

- [x] Positive inventory strictly confirmed: 144 in-polygon events, 0 duplicates, full provenance.
- [x] Bbox-only (67) separated for sensitivity; text-only (43) completely excluded.
- [x] Temporal matching defined: monsoon-constrained window (June–Sept 2004–2022) with 15-day CHIRPS availability check.
- [x] District sampling feasibility empirically calculated: East Sikkim deficit identified ($29$ capacity vs $96$ target); regional rebalancing proposed.
- [x] Explicit spatial validation plan formulated: Leave-One-District-Out within regions + Cross-Region transfer.
- [x] PU learning semantics documented: Relative Susceptibility Index vs. uncalibrated probability; nominal metric deflation explained.
- [x] Multi-scale terrain features formulated ($1\text{ km}, 3\text{ km}, 5\text{ km}$); outlier sensitivity of $\max(\text{slope})$ vs $\text{slope\_p90}$ contrasted.
- [x] Measured CHIRPS sensitivity integrated ($1\text{ km}: \le 3.55\%$; $5\text{ km}: 10.5\%\text{--}17.7\%$).
- [x] Reproducibility criteria, schema, and output files defined.
- [x] Unresolved decisions explicitly enumerated.
- [x] Preserved all existing project files and test suites (53 tests pass, full suite 166 pass).
- [x] Saved to `reports/phase2_sampling_design.md`.
- [x] Paused for user review before implementation.
