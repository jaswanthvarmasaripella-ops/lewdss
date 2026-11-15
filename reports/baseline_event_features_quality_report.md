# Baseline Event-Feature Extraction Quality Report
## LEWDSS — SIH26001 · CSE326/CSE276 Course Project
### Phase 2 Preparation: Audited Event Inventory Feature Extraction Review
**Status: COMPLETED & VERIFIED — NO SYNTHETIC NEGATIVES CREATED — AWAITING USER REVIEW**
**Date: October 2026**

---

> [!IMPORTANT]
> **Academic & Methodological Scope Notice**
> This evaluation strictly operates on the **presence-only historical event inventory** from the Unified Global Landslide Catalogue (UGLC, ESSD 2024).
> - **No pseudo-absence or background points have been generated.**
> - **No unrecorded locations are assumed to be confirmed negatives.**
> - **No machine learning models have been trained.**
> - **No dynamic soil moisture measurements are claimed.**
> - All reported metrics reflect actual calculations against verified Copernicus GLO-30 DEM tiles and CHIRPS v2.0 rainfall crops.

---

## 1. Executive Summary

The baseline feature extraction pipeline ([`src/features/feature_pipeline.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/src/features/feature_pipeline.py)) was executed over the authoritative UGLC audited event catalog covering all six target districts.

| Metric | Measured Value | Analysis & Notes |
|---|:---:|---|
| **Total District-Event Assignments** | **254** | Exact match with the reconnaissance audit baseline |
| **Unique Event IDs** | **252** | Exactly 2 events appear under two district audit lists |
| **Duplicate Event Assignments** | **2** | ID 888047 (border bbox overlap) & ID 888497 (text alias + spatial) |
| **Terrain Elevation & Slope Coverage** | **242 / 254 (95.28%)** | 100.0% coverage for confirmed spatial events (in-polygon + in-bbox) |
| **Rainfall Window Accumulation Coverage** | **253 / 254 (99.61%)** | 100.0% coverage for all true regional events; 1 missing due to Jaipur outlier |
| **District Attribution Breakdown** | **144 in-polygon, 67 in-bbox, 43 text-only** | Verified via pure-Python ray-casting on `target_districts.geojson` |
| **Rainfall Window Monotonicity** | **0 violations** | $R_{3\text{d}} \le R_{7\text{d}} \le R_{15\text{d}}$ verified across all 253 valid events |
| **Coordinate-to-Pixel Extraction Error** | **$0.00\times 10^0$** | Exact numerical match against independent raster read verification |

The processed dataset has been saved to:
- [`data/processed/baseline_event_features.csv`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/data/processed/baseline_event_features.csv) (254 rows $\times$ 14 columns)

---

## 2. Event Inventory & Assignment Breakdown

The 254 district-event assignments are distributed across the six target districts as follows:

```
District            Assignments   in-polygon   in-bbox   text-only   Day Precision
----------------------------------------------------------------------------------
Region A (Western Ghats):
  Wayanad (Kerala)           33           18        14           1          100.0%
  Idukki (Kerala)            69           51        17           1          100.0%
  Kodagu (Karnataka)         28            9        16           3          100.0%
  Subtotal Region A         130           78        47           5          100.0%

Region B (Northeast):
  East Sikkim                49           32         5          12          100.0%
  West Sikkim                25           13         3           9          100.0%
  East Khasi Hills (Megh.)   50           21        12          17          100.0%
  Subtotal Region B         124           66        20          38          100.0%
----------------------------------------------------------------------------------
TOTAL                       254          144        67          43          100.0%
```

### 2.1 Investigation of the Two Duplicate Event Assignments

Out of 254 total assignments, there are 252 unique UGLC event IDs. Two events are assigned to multiple districts:

1. **Event ID 888047 (Wayanad & Kodagu)**:
   - **Coordinates**: $(75.8087^\circ\text{E}, 11.9670^\circ\text{N})$
   - **Date**: 2018-08-01
   - **Locality Note**: *"Aralam forest in Kannur district"*
   - **Reason**: The bounding box for Wayanad ($75.78^\circ\text{--}76.45^\circ\text{E}, 11.45^\circ\text{--}11.98^\circ\text{N}$) and the bounding box for Kodagu ($75.35^\circ\text{--}76.18^\circ\text{E}, 11.93^\circ\text{--}12.85^\circ\text{N}$) overlap along the Kerala–Karnataka border between latitudes $11.93^\circ\text{N}$ and $11.98^\circ\text{N}$. The event coordinate falls inside both bounding boxes. When evaluated against strict district boundary polygons, it is classified as `in_bbox` for both districts.

2. **Event ID 888497 (Idukki & Wayanad)**:
   - **Coordinates**: $(77.0133^\circ\text{E}, 9.8738^\circ\text{N})$
   - **Date**: 2007-07-16
   - **Locality Note**: *"GFLD, locality: Wayanad and Idukki districts"*
   - **Reason**: The physical coordinates place this event inside Idukki's polygon near Munnar (`in_polygon` under Idukki). However, because the newspaper report text mentioned *"Wayanad and Idukki districts"*, the UGLC text search matched the keyword *"Wayanad"*, assigning it as a `text_only` match in Wayanad.

---

## 3. Spatial Attribution & Missing Feature Analysis

The pipeline classifies each event's spatial attribution into three mutually exclusive categories:
- **`in_polygon`**: Point lies strictly inside the official district boundary polygon.
- **`in_bbox`**: Point lies outside the polygon but inside the district's rectangular bounding box (border corridor).
- **`text_only`**: Point lies outside the bounding box, attributed solely by text/newspaper locality alias.

### 3.1 Cross-Tabulation of Attribution vs. Data Availability

```
Spatial Match Type     Total Events   DEM Available (%)   Rain Available (%)
----------------------------------------------------------------------------
in_polygon                      144      144 (100.0%)        144 (100.0%)
in_bbox                          67       67 (100.0%)         67 (100.0%)
text_only                        43       31  (72.1%)         42  (97.7%)
----------------------------------------------------------------------------
Total                           254      242  (95.3%)        253  (99.6%)
```

> [!NOTE]
> For all **211 geographically verified events** (`in_polygon` + `in_bbox`), feature coverage is **100.0% complete** for both Copernicus DEM elevation/slope and CHIRPS rainfall.

### 3.2 Root Cause of the 12 Missing DEM Features

All 12 events where `dem_available == False` are in the `text_only` category. They fall outside the 11 acquired Copernicus DEM tiles:
- **1 event in Region A (ID 888275)**: Coords $(76.83^\circ\text{E}, 8.98^\circ\text{N})$ located in Kollam district, Kerala, south of tile N09_E076 (origin $9.0^\circ\text{N}$).
- **1 event in Region B (ID 888048)**: Coords $(75.81^\circ\text{E}, 26.88^\circ\text{N})$ located in **Jaipur, Rajasthan** (a geocoding error in the original catalogue due to a news release dateline).
- **1 event in Region B (ID 938356)**: Coords $(88.44^\circ\text{E}, 26.94^\circ\text{N})$ located in Sevoke/Kalimpong, West Bengal, south of tile N27_E088.
- **7 events in Region B (IDs 1048288–1048292, 1048308)**: Coords in West/South Garo Hills, Meghalaya ($90.2^\circ\text{--}90.5^\circ\text{E}$), west of tile N25_E091 (origin $91.0^\circ\text{E}$); matched via newspaper text *"The Shillong Times"*.
- **2 events in Region B (IDs 1048503, 1048515)**: Coords at $(91.86^\circ\text{E}, 26.05^\circ\text{--}26.10^\circ\text{N})$ near Jorabat / Byrnihat along the Assam border, north of tile N25_E091.

### 3.3 Root Cause of the 1 Missing Rainfall Feature

The only event where `rain_available == False` is **ID 888048**.
- Its catalogued coordinates are in Jaipur, Rajasthan ($75.81^\circ\text{E}, 26.88^\circ\text{N}$).
- Region B's CHIRPS regional crop spans $88.00^\circ\text{--}93.00^\circ\text{E}$ and $24.50^\circ\text{--}28.50^\circ\text{N}$.
- The coordinate falls outside the regional crop boundary, correctly returning `NaN` without silent imputation.

---

## 4. Verification of Coordinate Extraction & Rainfall Windows

Two representative events from Region A and Region B were subjected to independent, ground-truth manual verification:

### 4.1 Region A Verification: Event 888036 (Wayanad, Kerala)
- **Date**: 2018-08-08
- **Coordinates**: $(75.795925^\circ\text{E}, 11.740458^\circ\text{N})$
- **District**: Wayanad (`in_polygon`)

**Daily CHIRPS Crop Values ($t-14$ to $t$):**
- 2018-07-25 to 2018-07-29: $0.00\text{ mm}$
- 2018-07-30: $100.71\text{ mm}$
- 2018-07-31: $67.14\text{ mm}$
- 2018-08-01 to 2018-08-02: $0.00\text{ mm}$
- 2018-08-03: $71.78\text{ mm}$
- 2018-08-04 to 2018-08-06: $0.00\text{ mm}$
- 2018-08-07: $14.17\text{ mm}$
- 2018-08-08 (Event Day): $70.87\text{ mm}$

**Window Sum Comparison:**
- **3-day window** (Aug 06 – Aug 08): Manual sum $= 85.0474\text{ mm}$ | Pipeline $= 85.0474\text{ mm}$ | Difference $= 0.00\times 10^0$
- **7-day window** (Aug 02 – Aug 08): Manual sum $= 156.8276\text{ mm}$ | Pipeline $= 156.8276\text{ mm}$ | Difference $= 0.00\times 10^0$
- **15-day window** (Jul 25 – Aug 08): Manual sum $= 324.6703\text{ mm}$ | Pipeline $= 324.6703\text{ mm}$ | Difference $= 0.00\times 10^0$

**Copernicus DEM Elevation & Slope Comparison:**
- Tile: `Copernicus_DSM_COG_10_N11_00_E075_00_DEM.tif`
- Manual Elevation $= 872.9678\text{ m}$ | Pipeline $= 872.9678\text{ m}$ | Difference $= 0.00\times 10^0$
- Manual Slope $= 27.5641^\circ$ | Pipeline $= 27.5641^\circ$ | Difference $= 0.00\times 10^0$

### 4.2 Region B Verification: Event 938381 (East Sikkim)
- **Date**: 2007-09-07
- **Coordinates**: $(88.4883^\circ\text{E}, 27.2010^\circ\text{N})$
- **District**: East Sikkim (`in_polygon`)

**Window Sum Comparison:**
- **3-day window**: Manual sum $= 42.5780\text{ mm}$ | Pipeline $= 42.5780\text{ mm}$ | Difference $= 0.00\times 10^0$
- **7-day window**: Manual sum $= 92.9858\text{ mm}$ | Pipeline $= 92.9858\text{ mm}$ | Difference $= 1.42\times 10^{-14}$
- **15-day window**: Manual sum $= 191.9141\text{ mm}$ | Pipeline $= 191.9141\text{ mm}$ | Difference $= 0.00\times 10^0$

**Copernicus DEM Elevation & Slope Comparison:**
- Tile: `Copernicus_DSM_COG_10_N27_00_E088_00_DEM.tif`
- Manual Elevation $= 382.9641\text{ m}$ | Pipeline $= 382.9641\text{ m}$ | Difference $= 0.00\times 10^0$
- Manual Slope $= 36.0227^\circ$ | Pipeline $= 36.0227^\circ$ | Difference $= 0.00\times 10^0$

---

## 5. Statistical Profile of Verified Historical Landslide Events

Summary statistics for the **144 verified in-polygon events**:

| Feature | Units | Min | 25% | Median | 75% | Max | Mean | Std Dev |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Elevation** | $\text{m}$ | 54.4 | 674.3 | 1014.4 | 1632.7 | 4192.2 | 1188.2 | 744.9 |
| **Slope** | $\text{deg}$ | 0.0 | 9.7 | 19.3 | 29.8 | 55.6 | 20.7 | 13.8 |
| **Rainfall (3-day)** | $\text{mm}$ | 0.0 | 25.1 | 70.0 | 125.0 | 375.9 | 86.8 | 79.1 |
| **Rainfall (7-day)** | $\text{mm}$ | 0.0 | 48.2 | 108.9 | 224.2 | 500.5 | 146.7 | 120.3 |
| **Rainfall (15-day)** | $\text{mm}$ | 0.0 | 106.7 | 211.9 | 362.5 | 744.7 | 247.6 | 170.0 |

**Observations:**
- The median slope for recorded landslides in the study areas is **$19.3^\circ$**, with an upper quartile of **$29.8^\circ$**.
- 15-day antecedent rainfall reaches up to **$744.7\text{ mm}$**, highlighting extreme monsoon-induced saturation as the dominant triggering mechanism.
- Zero events show negative rainfall or slopes $> 85^\circ$, confirming data sanitization integrity.

---

## 6. Recommendations & Methodological Boundaries for Phase 2

1. **Spatial Attribution Filter**: For model training and spatial cross-validation, the 43 `text_only` events should be excluded or segregated into a secondary sensitivity analysis because they lack confirmed polygon boundaries and 12 lack DEM coverage.
2. **Handling the 2 Duplicate Assignments**:
   - ID 888047 should be assigned to either Wayanad or Kodagu based on distance to district centroid, or evaluated in a merged Western Ghats regional model.
   - ID 888497 is geographically in Idukki (`in_polygon`) and should remain attributed strictly to Idukki.
3. **Presence-Background (PU) Design Ready**:
   - The verified positive baseline is established.
   - Background sampling must enforce spatial exclusion buffers around historical events (to avoid false negative labeling) and sample across monsoon temporal windows.
