# Baseline Dataset Spatial Attribution & Quality Review
## LEWDSS — SIH26001 · CSE326/CSE276 Course Project
### Focused Audit of the 254 Historical Landslide Event Assignments
**Status: COMPLETED & VERIFIED — NO SYNTHETIC NEGATIVES CREATED — AWAITING USER REVIEW**
**Date: October 2026**

---

> [!IMPORTANT]
> **Academic & Methodological Scope Notice**
> This review evaluates the **geographic attribution integrity** of the 254 event assignments extracted in Phase 1.4 from the Unified Global Landslide Catalogue (UGLC, ESSD 2024).
> - **No machine learning models have been trained.**
> - **No synthetic negative or pseudo-absence points have been generated.**
> - **No raw data files or baseline tables have been modified or deleted.**
> - Text-alias matches are **strictly barred** from being treated as confirmed geographic events.
> - All evaluations report actual calculations against verified district polygons in [`data/raw/boundaries/target_districts.geojson`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/data/raw/boundaries/target_districts.geojson).

---

## 1. Executive Summary

| Attribution Tier | Record Count | Unique Event IDs | Geographic Integrity | Recommended Role |
|---|:---:|:---:|---|---|
| **Strict In-Polygon (`in_polygon`)** | **144** | **144** | Point lies strictly inside official district polygon | **PRIMARY Positive Training Dataset** |
| **Bounding Box Only (`in_bbox`)** | **67** | **66\*** | Lies outside polygon, inside district bbox rectangle | **Secondary Sensitivity Benchmark** (Border Corridors) |
| **Text-Only Match (`text_only`)** | **43** | **43** | Lies outside bbox; matched via media keyword | **EXCLUDED** (Geographically unverified / Outliers) |
| **Unresolved Cases** | **0** | **0** | All 254 records classified with explicit provenance | Fully accounted for |
| **Total Audit Inventory** | **254** | **252** | Exact match with initial catalogue audit | Baseline preserved |

*\*Note: Duplicate Event ID 888047 falls into the bounding boxes of both Wayanad and Kodagu along the interstate border.*

---

## 2. Row-Level Classification & Spatial Demarcation

Each of the 254 assignments was audited against the six target district polygons using ray-casting point-in-geometry verification. The records fall into three distinct tiers:

```
District                    Total Assignments   Strict In-Polygon   BBox-Only   Text-Only
-----------------------------------------------------------------------------------------
Region A (Western Ghats):
  Wayanad (Kerala)                         33                  18          14           1
  Idukki (Kerala)                          69                  51          17           1
  Kodagu (Karnataka)                       28                   9          16           3
  Subtotal Region A                       130                  78          47           5

Region B (Northeast):
  East Sikkim                              49                  32           5          12
  West Sikkim                              25                  13           3           9
  East Khasi Hills (Meghalaya)             50                  21          12          17
  Subtotal Region B                       124                  66          20          38
-----------------------------------------------------------------------------------------
TOTAL                                     254                 144          67          43
```

### 2.1 Tier 1: Strict In-Polygon Matches (144 Records)
- **Definition**: The $(lon, lat)$ coordinate falls strictly inside the multi-vertex boundary polygon of the assigned district.
- **Data Quality**:
  - DEM elevation & slope coverage: **100.0%** (144 / 144).
  - CHIRPS rainfall window coverage: **100.0%** (144 / 144).
  - Duplicate events: **0** (all 144 IDs are unique).
- **Geographic Validity**: Highest possible confidence. These points represent historical slope failures confirmed within the administrative jurisdiction of the emergency response authority.

### 2.2 Tier 2: Bounding Box Only Matches (67 Records)
- **Definition**: The coordinate falls outside the district boundary polygon, but within the minimum bounding rectangle $[min\_lon, min\_lat, max\_lon, max\_lat]$ of the district.
- **Proximity Analysis**:
  - **Median distance to district boundary**: **3.17 km** (mean $= 6.08\text{ km}$).
  - $\le 2\text{ km}$ from boundary: **19 events** (28.4%).
  - $2\text{--}5\text{ km}$ from boundary: **23 events** (34.3%).
  - $5\text{--}10\text{ km}$ from boundary: **6 events** (9.0%).
  - $10\text{--}20\text{ km}$ from boundary: **19 events** (28.4%).
- **Nature of Border Events**:
  - Many represent critical **lifeline transportation corridors** directly serving the target districts:
    - *Yedekumeri Railway Station, Shiradi Ghat* (Kodagu/Hassan border rail line, NH-75).
    - *Sakaleshpur–Subrahmanya Ghat section* (lifeline access to Kodagu).
    - *Aralam Forest corridor* (Kannur–Wayanad border pass).
    - *Vimala City / Adimali ghats* (Kottayam/Idukki boundary).
- **Data Quality**: 100.0% DEM and rainfall coverage (all lie within the regional raster crops).

### 2.3 Tier 3: Text-Only Matches (43 Records)
- **Definition**: The coordinate falls completely outside the district bounding box. The record was pulled during initial keyword screening because the catalog narrative, locality string, or newspaper dateline mentioned the district name or alias.
- **Proximity Analysis**:
  - **Median distance to district boundary**: **19.9 km** (mean $= 70.4\text{ km}$, max $= 1,250.4\text{ km}$).
  - $> 100\text{ km}$ from assigned district: **8 events**!
- **Fatal Data Quality Deficiencies**:
  - **12 events have NO DEM coverage** (`NaN`), as they fall outside the 11 acquired Copernicus DEM tiles.
  - **1 event has NO CHIRPS rainfall coverage** (`NaN`), located in Jaipur, Rajasthan.
- **Methodological Rule**: In accordance with scientific integrity and viva defense standards, **text-only matches must NEVER be treated as verified geographic events**. They are formally excluded from primary model training.

---

## 3. Investigation of Duplicate Event IDs

Out of 254 assignments, exactly two event IDs appear more than once in the inventory.

### 3.1 Event ID 888047 (`Wayanad` vs. `Kodagu`)

| Property | Wayanad Assignment | Kodagu Assignment |
|---|---|---|
| **Catalogue ID** | `888047` | `888047` |
| **Coordinates** | $(75.8087^\circ\text{E}, 11.9670^\circ\text{N})$ | $(75.8087^\circ\text{E}, 11.9670^\circ\text{N})$ |
| **Event Date** | 2018-08-01 | 2018-08-01 |
| **Catalogue Locality** | *"Aralam forest in Kannur district"* | *"Aralam forest in Kannur district"* |
| **Attribution Match Type** | `in_bbox` (distance $= 2.45\text{ km}$) | `in_bbox` (distance $= 3.86\text{ km}$) |
| **Strict Polygon Status** | Outside Wayanad polygon | Outside Kodagu polygon |

**Provenance & Analysis:**
- The Kannur district border corridor wedges between Wayanad (to the south) and Kodagu (to the north).
- Latitudes $11.93^\circ\text{N}$ to $11.98^\circ\text{N}$ fall within the bounding boxes of both districts.
- The physical slip occurred in Aralam Wildlife Sanctuary in Kannur district, $2.45\text{ km}$ from the Wayanad boundary and $3.86\text{ km}$ from the Kodagu boundary.

**Defensible Attribution Decision:**
- **Primary Dataset (`in_polygon`)**: Naturally **excluded from both** districts because it does not lie inside either polygon.
- **Sensitivity Benchmark (`in_bbox`)**: Attributed primarily to **Wayanad** (closer by geodesic distance: $2.45\text{ km}$ vs $3.86\text{ km}$), or retained as a shared border corridor event with explicit deduplication.

---

### 3.2 Event ID 888497 (`Idukki` vs. `Wayanad`)

| Property | Idukki Assignment | Wayanad Assignment |
|---|---|---|
| **Catalogue ID** | `888497` | `888497` |
| **Coordinates** | $(77.0133^\circ\text{E}, 9.8738^\circ\text{N})$ | $(77.0133^\circ\text{E}, 9.8738^\circ\text{N})$ |
| **Event Date** | 2007-07-16 | 2007-07-16 |
| **Catalogue Locality** | *"GFLD, locality: Wayanad and Idukki districts"* | *"GFLD, locality: Wayanad and Idukki districts"* |
| **Attribution Match Type** | **`in_polygon`** (distance $= 0.00\text{ km}$) | **`text_only`** (distance $= 198.84\text{ km}$) |
| **Strict Polygon Status** | **Inside Idukki polygon (Munnar)** | Outside Wayanad polygon |

**Provenance & Analysis:**
- The physical event coordinates $(77.0133^\circ\text{E}, 9.8738^\circ\text{N})$ place this landslide squarely within Devikulam / Munnar taluk in Idukki district.
- The newspaper report narrative summarized monsoon damage across multiple Kerala districts: *"At least eight persons were killed in landslides in Wayanad and Idukki districts..."*
- Automated catalog scraping matched the keyword *"Wayanad"*, assigning the event to Wayanad as a text alias despite the coordinates being in Idukki, nearly $200\text{ km}$ to the south.

**Defensible Attribution Decision:**
- **Primary Attribution**: **Idukki (`in_polygon`)**.
- The assignment under Wayanad is an unverified text artifact and is **permanently discarded** from Wayanad's inventory.

---

## 4. Proposed Primary Positive-Event Dataset

To ensure absolute methodological defensibility, we propose a clean two-tier dataset architecture:

### 4.1 Tier 1: Primary Positive Training Dataset (`dataset_v1_primary`)

```
Selection Rule: match_type == "in_polygon"
```

| District | Total Raw Assignments | Excluded Text-Only | Excluded BBox-Only | Retained Primary Positive Events |
|---|:---:|:---:|:---:|:---:|
| **Wayanad** | 33 | 1 | 14 | **18** |
| **Idukki** | 69 | 1 | 17 | **51** |
| **Kodagu** | 28 | 3 | 16 | **9** |
| **East Sikkim** | 49 | 12 | 5 | **32** |
| **West Sikkim** | 25 | 9 | 3 | **13** |
| **East Khasi Hills** | 50 | 17 | 12 | **21** |
| **Total** | **254** | **43** | **67** | **144** |

- **Total Rows**: **144**
- **Unique Event IDs**: **144** (100% unique, 0 duplicates)
- **DEM Feature Completeness**: **100.0%** (144 / 144)
- **Rainfall Feature Completeness**: **100.0%** (144 / 144)
- **Geographic Ground Truth**: Verified inside target district boundaries.

#### Complete Accounting of Exclusions (110 records from 254):
1. **43 Text-Only Exclusions**:
   - 12 with missing DEM data (outside acquired 30m tiles).
   - 1 in Jaipur, Rajasthan (geocoding error in UGLC source).
   - 1 false text match in Wayanad (Event 888497, true location is Idukki).
   - 29 media dateline / newspaper mentions with coordinates in non-target districts (Garo Hills, Assam border, West Bengal).
2. **67 Bounding-Box Only Exclusions**:
   - Coordinates fall in neighboring districts (Kannur, Kozhikode, Hassan, South/North Sikkim, Ri-Bhoi, West Khasi Hills) that intersect the rectangular bounding box but lie outside the official administrative polygon.
   - Retained in audit logs for sensitivity analysis, but excluded from primary positive training labels.

---

### 4.2 Tier 2: Extended Sensitivity Dataset (`dataset_v1_extended_corridor`)

```
Selection Rule: match_type == "in_polygon" OR (match_type == "in_bbox" AND distance_to_poly_km <= 5.0)
```

- **Row Count**: **186** (144 in-polygon $+$ 42 proximal border events).
- **Unique Event IDs**: **185** (Event 888047 deduplicated to Wayanad based on nearest distance).
- **Purpose**: Evaluates model sensitivity when including border-zone landslides that severed lifeline transport corridors connecting target districts to neighboring plains.

---

## 5. Assessment of Point-Based Extraction vs. Positional Uncertainty

### 5.1 The Positional Uncertainty Problem

The UGLC catalogue has a documented positional uncertainty of **5–10 km**. In many instances, the recorded coordinates represent the centroid of the nearest town, taluk office, or road junction mentioned in media reports, rather than a GPS-surveyed slip scarp.

| Dimension | Point-Based Single Pixel | Physical Ground Truth | Viva Defense Vulnerability |
|---|---|---|---|
| **DEM Slope (30m)** | Samples 1 single $30\times30\text{ m}$ cell | Landslide scarps are on steep slopes ($25^\circ\text{--}45^\circ$) | Baseline data contains events with slope $= 0.0^\circ$ (town center geocode). A classifier trained on single pixels learns that flat valley bottoms produce landslides! |
| **DEM Elevation (30m)** | Samples elevation at valley floor | Landslide origins are hundreds of meters up the valley wall | Underestimates gravitational potential energy. |
| **CHIRPS Rainfall (5.5 km)** | Samples 1 $0.05^\circ$ cell | Synoptic monsoon precipitation spans $50\text{--}200\text{ km}$ | **Robust.** A 5 km positional shift alters rainfall by $< 5\%$. Rainfall is scale-appropriate. |

### 5.2 Recommendation: Multi-Scale Zonal Buffer Aggregation (Phase 2)

Rather than naive single-pixel sampling, we recommend deriving **zonal buffer features** centered at the recorded coordinate with radii matching the uncertainty envelope ($1\text{ km}$, $3\text{ km}$, $5\text{ km}$):

$$\text{slope\_max}_{R} = \max_{(x,y) \in \mathcal{B}_R} \text{slope}(x, y)$$

$$\text{slope\_p90}_{R} = \text{Percentile}_{90}\left(\{\text{slope}(x, y) \mid (x,y) \in \mathcal{B}_R\}\right)$$

$$\text{elev\_relief}_{R} = \max_{(x,y) \in \mathcal{B}_R} \text{elev}(x, y) - \min_{(x,y) \in \mathcal{B}_R} \text{elev}(x, y)$$

**Scientific Justification for Viva:**
1. Even if the reported point is in the valley center, a $3\text{ km}$ buffer captures whether steep, failure-prone slopes ($> 25^\circ$) exist in the immediate vicinity.
2. `elev_relief` serves as a direct proxy for topographic relief and available gravitational potential energy.
3. Completely transparent, deterministic, and requires no external packages.

*(Note: In accordance with instructions, this recommendation is documented for Phase 2 implementation and has NOT been executed yet).*

---

## 6. Verification of Event-Date Rainfall Windows

The rainfall accumulation logic in [`src/features/feature_pipeline.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/src/features/feature_pipeline.py) was verified:

1. **Backwards Window Formulation**:
   - $3\text{-day window}$: $\{t-2, t-1, t\}$ (3 days inclusive of event day $t$).
   - $7\text{-day window}$: $\{t-6, \dots, t\}$ (7 days inclusive).
   - $15\text{-day window}$: $\{t-14, \dots, t\}$ (15 days inclusive).
2. **Missingness & NoData Handling**:
   - If any single daily TIFF in the window is missing from disk, the accumulation function strictly returns `None` (`NaN`).
   - If the query coordinate falls outside the valid CHIRPS regional crop, it returns `None` (`NaN`).
   - CHIRPS nodata pixels (value $-9999.0$) are filtered; sub-zero values are clamped.
3. **Monotonicity Verification**:
   - Calculated for all 253 valid events: $R_{3\text{d}} \le R_{7\text{d}} \le R_{15\text{d}}$.
   - **Monotonicity violations**: **0**.

---

## 7. Automated Test Verification

All tests in [`tests/test_uglc_audit.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/tests/test_uglc_audit.py) and [`tests/test_feature_pipeline.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI%20project/tests/test_feature_pipeline.py) pass cleanly.
- Full test suite: **166 tests passing in 16.73s**.
- Duplicate event 888497 containment inside Idukki's polygon confirmed by automated test.

---

## 8. Summary Checklist & Phase 2 Transition

- [x] Inspected `baseline_event_features.csv` and quality report.
- [x] Audited all 254 assignments row-by-row with original IDs and districts preserved.
- [x] Separated into strict in-polygon (144), bbox-only (67), text-only (43), and unresolved (0).
- [x] Barred text-only matches from being treated as verified geographic events.
- [x] Investigated duplicates: 888047 (border corridor bbox overlap) and 888497 (Idukki in-polygon vs Wayanad text alias).
- [x] Defined Proposed Primary Positive Dataset: **144 strict in-polygon events (144 unique IDs)**.
- [x] Documented complete accounting for all 110 exclusions.
- [x] Assessed point-based features vs. 5–10 km location uncertainty; recommended multi-scale zonal buffer summaries.
- [x] Verified backwards rainfall accumulation windows and nodata handling.
- [x] Saved findings to `reports/baseline_attribution_review.md`.
- [x] All 166 automated tests passing.
- [x] Stopped before implementing background sampling.
