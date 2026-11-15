# Phase 2 Dataset Construction & Feature Pipeline Verification Report
## LEWDSS — SIH26001 · CSE326/CSE276 Course Project
### Phase 2: Presence-Background Dataset Construction, Multi-Scale Terrain Features, and Verification
**Status: PHASE 2 COMPLETE — DATASET GENERATED & VERIFIED — READY FOR PHASE 3 PLANNING**
**Date: October 2026**

---

> [!IMPORTANT]
> **Advisory Scope & Academic Integrity Notice**
> This report documents the generation and automated verification of the **Phase 2 Unified Feature Dataset** (`dataset_v1_features.csv`).
> - **No machine learning models have been trained.**
> - **No synthetic negatives were created; background points are modeled as unlabeled ($s = 0$) under a formal Presence-Unlabeled (PU) framework.**
> - **No new packages or external datasets were downloaded.**
> - All reported metrics, spatial distances, and feature distributions reflect real, verified measurements.

---

## 1. Executive Summary

| Verification Item | Measured Value | Target Criterion | Status |
|---|:---:|:---:|:---:|
| **Total Dataset Size** | **576 samples** (28 columns) | 144 positives + 432 background | **PASS** |
| **Primary Positive Events** | **144 events** (100% unique IDs) | Strict in-polygon, 0 duplicates | **PASS** |
| **Background Samples** | **432 samples** | Exact target quota (1:3 ratio) | **PASS** |
| **Positive Exclusion Buffer** | **$\ge 5.0\text{ km}$** (measured min: $5.008\text{ km}$) | Min $5.0\text{ km}$ exclusion zone | **PASS** |
| **Inter-Background Spacing** | **$\ge 3.0\text{ km}$** (measured min: $3.004\text{ km}$) | Min $3.0\text{ km}$ separation | **PASS** |
| **Polygon Containment** | **576 / 576 (100.0%)** | Strict in-polygon containment | **PASS** |
| **Date-Paired Temporal Window** | **100.0% valid** (15-day CHIRPS verified) | Active monsoon period (2004–2022) | **PASS** |
| **Feature Completeness** | **576 / 576 (100.0%)** | 0 missing values across all columns | **PASS** |
| **Rainfall Window Monotonicity** | **0 violations** ($R_{3\text{d}} \le R_{7\text{d}} \le R_{15\text{d}}$) | Strict monotonic accumulation | **PASS** |
| **Full Project Test Suite** | **177 / 177 passing** in 26.22s | Zero regressions across all tests | **PASS** |

The completed data assets have been saved to:
- [`data/processed/dataset_v1_features.csv`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/data/processed/dataset_v1_features.csv) (576 rows $\times$ 28 columns)
- [`data/processed/dataset_v1_bbox_corridor.csv`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/data/processed/dataset_v1_bbox_corridor.csv) (67 bbox-only events separated for sensitivity testing)
- [`data/processed/dataset_v1_metadata.json`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/data/processed/dataset_v1_metadata.json) (complete provenance, configuration, and audit metadata)

---

## 2. District-Level Sample Distribution & Quota Adherence

Through the approved **Regional Quota Rebalancing (Decision 1, Option A)**, background samples were generated using seed 42 without violating spatial independence:

```
District                    Positives (is_positive=1)   Background (is_positive=0)   Total Samples   Ratio
----------------------------------------------------------------------------------------------------------
Region A (Western Ghats):
  Wayanad (Kerala)                                18                           54              72   1:3.0
  Idukki (Kerala)                                 51                          153             204   1:3.0
  Kodagu (Karnataka)                               9                           27              36   1:3.0
  Subtotal Region A                               78                          234             312   1:3.0

Region B (Northeast):
  East Sikkim                                     32                           28              60   1:0.9*
  West Sikkim                                     13                           55              68   1:4.2*
  East Khasi Hills (Meghalaya)                    21                          115             136   1:5.5*
  Subtotal Region B                               66                          198             264   1:3.0
----------------------------------------------------------------------------------------------------------
TOTAL                                            144                          432             576   1:3.0
```

*\*Note on Region B Rebalancing: As established during sampling feasibility testing, East Sikkim's compact area ($940.7\text{ km}^2$) with 32 clustered landslides eliminated $66.2\%$ of the district under $5\text{ km}$ exclusion. Capping East Sikkim at its physical capacity (28 points) and reallocating to West Sikkim and East Khasi Hills successfully preserved the $1:3$ regional ratio (198 background points) while maintaining $100\%$ compliance with the $5\text{ km}$ exclusion and $3\text{ km}$ spacing rules.*

---

## 3. Spatial & Temporal Constraint Verification

### 3.1 Spatial Exclusion & Separation Audit
- **Positive Event Exclusion**: Every background point was tested against all positive events in its district. The minimum observed distance across all 432 background points was **$5.008\text{ km}$**, confirming zero violation of the $5.0\text{ km}$ buffer.
- **Inter-Sample Spacing**: Pairwise geodesic distance calculations within each district confirmed that the minimum observed inter-background spacing was **$3.004\text{ km}$**, confirming zero violation of the $3.0\text{ km}$ spacing rule.
- **Boundary Containment**: All 576 points passed pure-Python ray-casting point-in-geometry verification against the strict GeoJSON polygons.

### 3.2 Date-Paired Co-occurrence Verification
- Every background point inherited the exact event date of a historical landslide from that district.
- Every assigned date was verified to possess unbroken, non-corrupt daily CHIRPS GeoTIFF crops on disk for all 15 antecedent days ($\{t-14, \dots, t\}$).
- **Viva Defense Significance**: This ensures that when the classifier compares positive events to background points, it is evaluating conditions during verified active monsoon periods rather than trivially differentiating between monsoon rain and dry winter months.

---

## 4. Multi-Scale Feature Engineering & Distribution Analysis

### 4.1 Statistical Distributions: Positives vs. Background

| Feature Name | Feature Type | Positives Median (n=144) | Background Median (n=432) | Physical Interpretation |
|---|---|:---:|:---:|---|
| `elevation_m` | Point Terrain | $1,014.4\text{ m}$ | $1,010.5\text{ m}$ | Broad regional elevation overlap |
| `slope_deg` | Point Terrain | $19.31^\circ$ | $16.57^\circ$ | Positives show higher median slope |
| `slope_p90_1km` | 1 km Buffer Zonal | $31.18^\circ$ | $30.20^\circ$ | Prevailing steepness in immediate vicinity |
| `slope_p90_3km` | 3 km Buffer Zonal | $32.13^\circ$ | $31.89^\circ$ | Mesoscale valley wall steepness |
| `slope_p90_5km` | 5 km Buffer Zonal | $32.14^\circ$ | $32.68^\circ$ | Regional mountain terrain envelope |
| `elev_relief_3km`| 3 km Buffer Zonal | $751.3\text{ m}$ | $750.0\text{ m}$ | Gravitational potential energy |
| `rain_15d_mm` | Point Rainfall | $211.87\text{ mm}$ | $227.08\text{ mm}$ | Antecedent 15-day saturation |
| `rain_3km_mean_15d` | 3 km Areal Rainfall | $213.20\text{ mm}$ | $227.08\text{ mm}$ | Spatially regularized antecedent rain |

### 4.2 Single-Pixel vs. Multi-Scale Zonal Statistics (The Positional Uncertainty Fix)

1. **Failure of Single-Pixel Slope**:
   - In the baseline single-pixel extraction, several positive landslide events had a recorded slope of **$0.0^\circ$** because coordinates were geocoded to town/village centers in the valley bottom.
2. **Resolution via Zonal Buffering**:
   - When evaluated across the $1\text{ km}$ buffer, the 90th-percentile slope for these same points rises to **$> 25^\circ$**, capturing the true steep, failure-prone mountain slopes surrounding the town.
   - At the $3\text{ km}$ and $5\text{ km}$ scales, elevation relief reaches **$> 750\text{ m}$**, confirming that high gravitational potential energy exists within the positional uncertainty envelope.
3. **Outlier Robustness of Percentile Slope**:
   - While $\text{slope\_max}$ can spike to $65^\circ\text{--}75^\circ$ due to single cliff-edge artifacts, $\text{slope\_p90}$ provides a robust, non-parametric decile gradient that is resilient to sensor noise.

---

## 5. Unified Dataset Schema Specification

The generated dataset ([`dataset_v1_features.csv`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/data/processed/dataset_v1_features.csv)) adheres to the following strict 28-column schema:

```
Col  Field Name          Type      Units      Source      Description
-------------------------------------------------------------------------------------------------------
1    sample_id           str       -          Pipeline    Unique identifier (e.g., POS_888036, BKG_IDUKKI_001)
2    is_positive         int       {0, 1}     PU Frame    1 = Historical Landslide; 0 = Unlabeled Background
3    event_id            str/null  -          UGLC        Original UGLC ID (null for background)
4    event_date          str (ISO) YYYY-MM-DD UGLC/Sample Event date or paired monsoon date
5    lon                 float     degrees E  WGS84       Longitude coordinate (EPSG:4326)
6    lat                 float     degrees N  WGS84       Latitude coordinate (EPSG:4326)
7    district            str       -          GeoJSON     Target district name
8    region              str       -          Config      Region A (Western Ghats) or Region B (Northeast)
9    match_type          str       -          GeoJSON     in_polygon (100% verified)

-- Baseline Point Features --
10   elevation_m         float     metres     Copernicus  Point elevation from 30m DEM
11   slope_deg           float     degrees    Copernicus  Horn's 3x3 point slope from 30m DEM
12   rain_3d_mm          float     mm         CHIRPS      3-day cumulative point rainfall ending on event_date
13   rain_7d_mm          float     mm         CHIRPS      7-day cumulative point rainfall ending on event_date
14   rain_15d_mm         float     mm         CHIRPS      15-day cumulative point rainfall ending on event_date

-- Multi-Scale DEM Zonal Features --
15   slope_max_1km       float     degrees    Copernicus  Maximum slope within 1 km circular buffer
16   slope_p90_1km       float     degrees    Copernicus  90th-percentile slope within 1 km circular buffer
17   elev_relief_1km     float     metres     Copernicus  Elevation relief (max - min) within 1 km buffer
18   slope_max_3km       float     degrees    Copernicus  Maximum slope within 3 km circular buffer
19   slope_p90_3km       float     degrees    Copernicus  90th-percentile slope within 3 km circular buffer
20   elev_relief_3km     float     metres     Copernicus  Elevation relief (max - min) within 3 km buffer
21   slope_max_5km       float     degrees    Copernicus  Maximum slope within 5 km circular buffer
22   slope_p90_5km       float     degrees    Copernicus  90th-percentile slope within 5 km circular buffer
23   elev_relief_5km     float     metres     Copernicus  Elevation relief (max - min) within 5 km buffer

-- 3 km Areal Mean Rainfall Features --
24   rain_3km_mean_3d    float     mm         CHIRPS      3 km buffer area-mean 3-day rainfall
25   rain_3km_mean_7d    float     mm         CHIRPS      3 km buffer area-mean 7-day rainfall
26   rain_3km_mean_15d   float     mm         CHIRPS      3 km buffer area-mean 15-day rainfall

-- Quality & Verification Flags --
27   dem_available       bool      -          Pipeline    True (100% complete)
28   rain_available      bool      -          Pipeline    True (100% complete)
```

---

## 6. Automated Testing Verification

An automated verification test suite was implemented in [`tests/test_phase2_dataset.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/tests/test_phase2_dataset.py).
- **New Phase 2 Tests**: **11 passed in 0.79s**
  - `test_positive_count_and_unique_ids`: Confirms exactly 144 unique positive events.
  - `test_positives_strictly_in_polygon`: Confirms all 144 positives are inside district polygons.
  - `test_background_sample_count`: Confirms exactly 432 background samples.
  - `test_district_quotas_satisfied`: Confirms all 6 district target quotas are met without deficits.
  - `test_background_strictly_in_polygon`: Confirms all 432 background points are inside district polygons.
  - `test_5km_exclusion_from_positives`: Mathematically verifies distance $\ge 5.0\text{ km}$ from every positive.
  - `test_3km_inter_background_spacing`: Mathematically verifies pairwise distance $\ge 3.0\text{ km}$.
  - `test_zero_missing_values_across_features`: Confirms 0 missing values across all features.
  - `test_rainfall_window_monotonicity`: Confirms $R_{3\text{d}} \le R_{7\text{d}} \le R_{15\text{d}}$ for both point and buffer rainfall.
  - `test_zonal_slope_consistency`: Confirms $\text{slope\_max} \ge \text{slope\_p90}$ and $\text{relief} \ge 0$.
  - `test_sampler_deterministic_reproducibility`: Confirms seed 42 produces identical coordinates.
- **Full Project Test Suite**: **177 passed in 26.22s** (zero regressions across ingestion, CHIRPS crops, DEM tiles, UGLC audit, and feature pipeline).

---

## 7. Explicit Methodological Boundaries for Viva Defense

1. **Presence-Unlabeled Semantics**:
   - Background samples are **unlabeled ($s = 0$)**, not verified non-events ($y = 0$).
   - In any future modeling, predicted outputs represent a **Relative Landslide Susceptibility Index (RLSI)**, **never** a "calibrated real-world probability of failure".
2. **Dynamic Triggering vs. Year-Round Prediction**:
   - Because background samples were assigned dates from historical monsoon periods, the dataset evaluates **relative discrimination under event-associated monsoon conditions**, not year-round occurrence prediction.
3. **Absence of Dynamic Soil Moisture**:
   - Antecedent precipitation (3-day, 7-day, 15-day CHIRPS) acts as a hydrologic proxy.
   - Dynamic volumetric soil moisture is not measured or claimed.

---

## 8. Summary Checklist

- [x] Primary positive inventory constructed: 144 strict in-polygon events, 0 duplicates.
- [x] Bbox-only records (67) saved separately in `dataset_v1_bbox_corridor.csv` for sensitivity testing.
- [x] Background sampler implemented with 5 km positive exclusion and 3 km inter-background spacing.
- [x] Regional Quota Rebalancing executed: 432 background samples (0 deficit across all 6 districts).
- [x] Date-paired co-occurrence applied with 15-day CHIRPS raster coverage verified.
- [x] Multi-scale DEM zonal features (1 km, 3 km, 5 km) extracted and verified.
- [x] Baseline point elevation and slope retained.
- [x] 3 km buffer mean CHIRPS rainfall extracted alongside point rainfall.
- [x] Feature completeness: 100% complete across all 576 rows (0 missing values).
- [x] 11 new automated tests written; full test suite (177 tests) passing cleanly.
- [x] Outputs saved to `data/processed/` and report written to `reports/phase2_dataset_verification_report.md`.
- [x] No models trained; stopped for user review before proceeding to Phase 3.
