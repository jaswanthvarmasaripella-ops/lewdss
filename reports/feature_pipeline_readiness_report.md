# Feature Pipeline Readiness Report
## LEWDSS — SIH26001 * CSE326/CSE276 Course Project
### Phase 1.4: Geospatial Alignment Audit & Feature Pipeline Preparation
**Status: PHASE 1.4 COMPLETE — PIPELINE IMPLEMENTED & TESTED — AWAITING USER REVIEW**
**Date: October 2026**

---

> [!IMPORTANT]
> **Advisory Scope & Non-Operational Disclaimer**
> All evaluations in this report are for research and academic prototyping under CSE326.
> No ML models have been trained, no synthetic negative examples have been created,
> and no soil moisture measurements are claimed. The feature pipeline operates on
> presence-only event data with documented 5–10 km positional uncertainty.

---

## 1. Executive Summary

| Audit Item | Status | Evidence |
|---|:---:|---|
| **DEM Tiles (11/11)** | **PASS** | All 11 Copernicus GLO-30 tiles acquired, covering all 6 target districts |
| **CHIRPS Rainfall Crops** | **PASS** | 3,080 regional crop files (1,540 dates × 2 regions), all validated |
| **District Boundaries** | **PASS** | 6 target district polygons in `target_districts.geojson`, all verified |
| **UGLC Event Catalog** | **PASS** | 3 spatial tiles, 254 target-district events with 100% day-level dates |
| **CRS Alignment** | **PASS** | Both DEM and CHIRPS use WGS84 (EPSG:4326); verified via GeoTIFF tags |
| **Pixel Size Consistency** | **PASS** | DEM: 0.000278° (~30 m), CHIRPS: 0.05° (~5.5 km); ratio 180:1 |
| **Spatial Coverage** | **PASS** | CHIRPS crops fully enclose all 6 district bounding boxes |
| **DEM Coverage** | **PASS** | All district polygons are fully covered by acquired DEM tiles |
| **Feature Pipeline Code** | **PASS** | `src/features/feature_pipeline.py` + `raster_io.py` implemented & tested |
| **Automated Tests** | **PASS** | 48/48 tests pass (unit, integration, alignment, real-data validation) |
| **NoData Handling** | **PASS** | DEM: 0 nodata pixels; CHIRPS: -9999.0 sentinel handled correctly |

---

## 2. Geospatial Alignment Audit Results

### 2.1 DEM Tile Inventory & Metadata

All 11 required Copernicus DEM GLO-30 tiles have been acquired and verified:

| Tile ID | Region | File | Dimensions | Origin (lon, lat) | Pixel Size | Extent (lon) | Extent (lat) | Elevation Range | NoData | File Size |
|---|---|---|:---:|:---:|:---:|---|---|---|:---:|:---:|
| N09_E076 | A | `region_a/` | 3600×3600 | (76.0, 10.0) | 0.000278° | 76.0–77.0 | 9.0–10.0 | -10.9 – 1522.1 m | 0 | 34.3 MB |
| N09_E077 | A | `region_a/` | 3600×3600 | (77.0, 10.0) | 0.000278° | 77.0–78.0 | 9.0–10.0 | 30.0 – 2004.3 m | 0 | 43.9 MB |
| N10_E076 | A | `region_a/` | 3600×3600 | (76.0, 11.0) | 0.000278° | 76.0–77.0 | 10.0–11.0 | -11.3 – 2084.6 m | 0 | 45.9 MB |
| N10_E077 | A | `region_a/` | 3600×3600 | (77.0, 11.0) | 0.000278° | 77.0–78.0 | 10.0–11.0 | 125.0 – 2680.2 m | 0 | 42.8 MB |
| N11_E075 | A | `region_a/` | 3600×3600 | (75.0, 12.0) | 0.000278° | 75.0–76.0 | 11.0–12.0 | -10.0 – 2043.7 m | 0 | 20.0 MB |
| N11_E076 | A | `region_a/` | 3600×3600 | (76.0, 12.0) | 0.000278° | 76.0–77.0 | 11.0–12.0 | 2.5 – 2632.7 m | 0 | 44.2 MB |
| N12_E075 | A | `region_a/` | 3600×3600 | (75.0, 13.0) | 0.000278° | 75.0–76.0 | 12.0–13.0 | -3.6 – 1736.8 m | 0 | 45.6 MB |
| N12_E076 | A | `region_a/` | 3600×3600 | (76.0, 13.0) | 0.000278° | 76.0–77.0 | 12.0–13.0 | 626.7 – 1332.0 m | 0 | 39.8 MB |
| N25_E091 | B | `region_b/` | 3600×3600 | (91.0, 26.0) | 0.000278° | 91.0–92.0 | 25.0–26.0 | -4.4 – 1962.3 m | 0 | 46.6 MB |
| N25_E092 | B | `region_b/` | 3600×3600 | (92.0, 26.0) | 0.000278° | 92.0–93.0 | 25.0–26.0 | 4.4 – 1711.8 m | 0 | 45.7 MB |
| N27_E088 | B | `region_b/` | 3600×3600 | (88.0, 28.0) | 0.000278° | 88.0–89.0 | 27.0–28.0 | 183.0 – 8564.3 m | 0 | 42.0 MB |

**CRS & Pixel Consistency:**
- All 11 tiles: **WGS84 (EPSG:4326)** geographic coordinates
- Uniform pixel size: **0.000277778°** (1 arcsecond, ~27–31 m depending on latitude)
- Uniform dimensions: **3600 × 3600** pixels per tile
- **Zero nodata pixels** across all tiles
- Tiles are **edge-adjacent** (sharing exact boundary coordinates), not overlapping

### 2.2 CHIRPS Regional Rainfall Crop Inventory

| Property | Region A (Western Ghats) | Region B (Northeast) |
|---|:---:|:---:|
| **Crop count** | 1,540 files | 1,540 files |
| **Grid dimensions** | 200 × 80 px | 80 × 100 px |
| **Pixel size** | 0.05° | 0.05° |
| **Origin (lon, lat)** | (73.5°E, 18.5°N) | (88.0°E, 28.5°N) |
| **Extent (lon)** | 73.50° – 77.50°E | 88.00° – 93.00°E |
| **Extent (lat)** | 8.50° – 18.50°N | 24.50° – 28.50°N |
| **NoData sentinel** | -9999.0 | -9999.0 |
| **Valid range** | 0.0 – 330+ mm/day | 0.0 – 250+ mm/day |
| **Date coverage** | 1,540 unique dates | 1,540 unique dates |
| **Date set match** | Identical across both regions | Identical across both regions |

> [!NOTE]
> 12 leftover `.tif.gz` compressed files remain in `data/raw/rainfall/`. These are intermediate download artifacts from dates that were successfully cropped. They do not affect the pipeline but can be cleaned up to save ~40 MB.

### 2.3 District Boundary Audit

| District | State | Region | Geometry | Vertices | BBox (lon) | BBox (lat) |
|---|---|---|---|:---:|---|---|
| Wayanad | Kerala | A | Polygon | 284 | 75.77° – 76.44° | 11.44° – 11.97° |
| Idukki | Kerala | A | Polygon | 664 | 76.62° – 77.40° | 9.26° – 10.35° |
| Kodagu | Karnataka | A | Polygon | 564 | 75.37° – 76.18° | 11.92° – 12.83° |
| East Sikkim | Sikkim | B | Polygon | 255 | 88.44° – 88.92° | 27.14° – 27.42° |
| West Sikkim | Sikkim | B | Polygon | 250 | 88.02° – 88.35° | 27.11° – 27.61° |
| East Khasi Hills | Meghalaya | B | Polygon | 504 | 91.35° – 92.16° | 25.12° – 25.69° |

---

## 3. Coverage Verification

### 3.1 CHIRPS Crop → District Coverage

All six target district bounding boxes are **fully enclosed** by their respective CHIRPS regional crops:

| District | CHIRPS Region | Coverage Status |
|---|---|:---:|
| Wayanad | Region A (73.5°–77.5°E, 8.5°–18.5°N) | **FULLY COVERED** |
| Idukki | Region A | **FULLY COVERED** |
| Kodagu | Region A | **FULLY COVERED** |
| East Sikkim | Region B (88.0°–93.0°E, 24.5°–28.5°N) | **FULLY COVERED** |
| West Sikkim | Region B | **FULLY COVERED** |
| East Khasi Hills | Region B | **FULLY COVERED** |

### 3.2 DEM Tile → District Coverage

| District | Required Tiles | Acquired | Coverage |
|---|---|:---:|:---:|
| Wayanad | N11_E075, N11_E076 | 2/2 | Union fully covers district bbox |
| Idukki | N09_E076, N09_E077, N10_E076, N10_E077 | 4/4 | Union fully covers district bbox |
| Kodagu | N11_E075, N11_E076, N12_E075, N12_E076 | 4/4 | Union fully covers district bbox |
| East Sikkim | N27_E088 | 1/1 | Single tile fully contains district |
| West Sikkim | N27_E088 | 1/1 | Single tile fully contains district |
| East Khasi Hills | N25_E091, N25_E092 | 2/2 | Union fully covers district bbox |

> [!TIP]
> Wayanad and Kodagu share tiles N11_E075 and N11_E076, so the 11 unique tiles cover all 6 districts without redundant downloads.

---

## 4. Cross-Raster Alignment Analysis

### 4.1 Alignment Architecture

```
DEM (Copernicus GLO-30)         CHIRPS (v2.0 Daily)
---------------------------     ---------------------------
CRS: WGS84 (EPSG:4326)         CRS: WGS84 (EPSG:4326)
Pixel: 0.000278° (~30 m)       Pixel: 0.05° (~5,500 m)
Grid: 3600×3600 per 1° tile    Grid: 200×80 (A) / 80×100 (B)
Origin: Integer-degree corners  Origin: Regional bbox corners
dtype: float32                  dtype: float32
NoData: None (solid terrain)    NoData: -9999.0
```

### 4.2 Key Finding: No Pixel-Level Alignment Required

The DEM and CHIRPS rasters occupy the same geographic coordinate reference system (WGS84) but have fundamentally different:
- **Pixel grids**: 180:1 resolution ratio means grids cannot be resampled 1:1
- **Spatial extents**: DEM covers 1°×1° tiles; CHIRPS covers 4°×10° (A) or 5°×4° (B) regions
- **Origins**: DEM origins are integer degree corners; CHIRPS origins are the config bounding box corners

**This is correct by design.** The feature pipeline extracts values by geographic coordinate `(lon, lat)` from each raster independently — there is no assumption of shared pixel indices.

### 4.3 Alignment Guarantee

The implemented pipeline in [`raster_io.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/src/features/raster_io.py) converts `(lon, lat)` → `(row, col)` using each raster's own geotransform:
```python
# DEM: col = (lon - origin_x) / dx,  row = (origin_y - lat) / dy
# CHIRPS: same formula with different origin and pixel spacing
```
This guarantees that a query at (77.06°E, 10.09°N) extracts the correct DEM elevation pixel AND the correct CHIRPS rainfall pixel, regardless of their different grid spacings.

---

## 5. Feature Pipeline Implementation Status

### 5.1 Completed Components

| Component | File | Status | Description |
|---|---|:---:|---|
| DEM tile reader | [`raster_io.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/src/features/raster_io.py) | **DONE** | Pillow-based GeoTIFF reader with coordinate lookup |
| DEM spatial index | [`raster_io.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/src/features/raster_io.py) | **DONE** | Multi-tile index resolving (lon,lat) → correct tile |
| Slope computation | [`raster_io.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/src/features/raster_io.py) | **DONE** | Horn's 3×3 gradient with latitude-corrected metric distances |
| CHIRPS crop reader | [`raster_io.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/src/features/raster_io.py) | **DONE** | Binary TIFF parser for minimal-format crops |
| Rainfall accumulation | [`feature_pipeline.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/src/features/feature_pipeline.py) | **DONE** | 3/7/15-day backward windows with missing-date propagation |
| Point-in-polygon | [`feature_pipeline.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/src/features/feature_pipeline.py) | **DONE** | Pure-Python ray-casting for Polygon & MultiPolygon |
| Event feature extraction | [`feature_pipeline.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/src/features/feature_pipeline.py) | **DONE** | Per-event extraction: elevation, slope, rain accumulations, district |
| Feature table builder | [`feature_pipeline.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/src/features/feature_pipeline.py) | **DONE** | Full pipeline: UGLC events → structured DataFrame |
| Feature validation | [`feature_pipeline.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/src/features/feature_pipeline.py) | **DONE** | Schema checks, range validation, coverage statistics |

### 5.2 Feature Table Schema

The pipeline produces a DataFrame with the following columns:

| Column | Type | Source | Description |
|---|---|---|---|
| `event_id` | str | UGLC | Unique event identifier |
| `event_date` | str (ISO) | UGLC | Event date (YYYY-MM-DD) |
| `lon` | float | UGLC | Event longitude (WGS84) |
| `lat` | float | UGLC | Event latitude (WGS84) |
| `district` | str | UGLC audit | Assigned district name |
| `region` | str | Config | Region A (Western Ghats) or Region B (Northeast) |
| `match_type` | str | Pipeline | Spatial attribution: `in_polygon`, `in_bbox`, or `text_only` |
| `elevation_m` | float | DEM | Terrain elevation at event point (metres) |
| `slope_deg` | float | DEM | Terrain slope at event point (degrees, Horn's 3×3) |
| `rain_3d_mm` | float | CHIRPS | 3-day cumulative rainfall ending on event date (mm) |
| `rain_7d_mm` | float | CHIRPS | 7-day cumulative rainfall ending on event date (mm) |
| `rain_15d_mm` | float | CHIRPS | 15-day cumulative rainfall ending on event date (mm) |
| `dem_available` | bool | Pipeline | Whether DEM data was available for this event |
| `rain_available` | bool | Pipeline | Whether all rainfall dates were available |

### 5.3 Design Decisions & Constraints

1. **No synthetic negatives**: The pipeline extracts features only for known UGLC events. It does NOT create pseudo-absences or treat unrecorded locations as confirmed non-events. This is a deliberate design choice documented in the module docstring.

2. **Soil texture kept separate**: Static soil texture (clay/sand/silt from SoilGrids) is not included in the current pipeline. It will be added when the SoilGrids acquisition is completed, and will be clearly labeled as a static geotechnical proxy, not dynamic soil moisture.

3. **Single-pixel extraction (current)**: The pipeline currently extracts a single DEM pixel at the event coordinate. The reconnaissance report documents that catalog positional uncertainty is 5–10 km, and recommends multi-scale zonal buffer aggregation for production use. This is flagged as a **RECOMMENDATION** for Phase 2, not implemented in Phase 1.4.

4. **No UTM reprojection**: Slope computation uses latitude-corrected metric distances in the geographic CRS rather than reprojecting to UTM. This is accurate to < 0.5% within the study regions and avoids introducing a `pyproj`/`rasterio` dependency.

---

## 6. Automated Test Results

### 6.1 Test Summary

```
============================= 48 passed in 10.31s =============================
```

All 48 tests pass across 9 test categories:

| Category | Tests | Status | Description |
|---|:---:|:---:|---|
| **A. Raster I/O** | 7 | 7/7 PASS | DEM tile loading, extent, containment, elevation, slope |
| **B. Date-Window Correctness** | 6 | 6/6 PASS | 3/7/15-day windows, month boundaries, missing dates |
| **C. Raster Alignment** | 3 | 3/3 PASS | Pixel ratio, nodata clamping, DEM nodata slope |
| **D. Event-to-Pixel Extraction** | 1 | 1/1 PASS | Full feature extraction with all columns |
| **E. Feature Table Validation** | 2 | 2/2 PASS | Schema validation, implausible slope flagging |
| **F. Point-in-Polygon** | 4 | 4/4 PASS | Polygon, MultiPolygon, holes |
| **G. DEM Coverage Gaps** | 2 | 2/2 PASS | Missing tile detection, dem_available flag |
| **H. Integration (Real Data)** | 3 | 3/3 PASS | Munnar elevation > 1000m, CHIRPS extraction, Idukki polygon |
| **I. Geospatial Alignment Audit** | 14 | 14/14 PASS | CRS, pixel sizes, tile coverage, CHIRPS coverage, date manifest |

### 6.2 Key Test Highlights

- **`test_m14_chirps_crops_1540_dates_both_regions`**: Verified that exactly 1,540 unique dates exist for both regions, and the date sets are identical.
- **`test_m14_chirps_crop_covers_all_region_a_districts`** & **`test_m14_chirps_crop_covers_all_region_b_districts`**: Each district's bounding box is verified to be fully enclosed by the corresponding CHIRPS crop extent.
- **`test_m14_all_11_dem_tiles_acquired`**: All 11 required tiles confirmed present on disk.
- **`test_m14_dem_tiles_edge_adjacent_not_overlapping`**: Tiles share exact boundary edges (expected for 1°×1° grid) but have no interior overlap.
- **`test_m14_real_dem_gangtok_elevation`**: Gangtok (88.61°E, 27.33°N) → elevation > 1000 m (verified from real N27_E088 tile).
- **`test_m14_real_dem_shillong_elevation`**: Shillong (91.88°E, 25.57°N) → elevation > 1000 m (verified from real N25_E091 tile).
- **`test_m14_rain_window_crosses_month_boundary`**: 15-day window ending Aug 5 correctly starts Jul 22, crossing the month boundary.

---

## 7. Presence-Only Catalog Limitations

> [!CAUTION]
> **The UGLC catalog is strictly presence-only.** The following limitations must be propagated to all downstream modeling and interpretation.

1. **No confirmed negatives**: Locations and dates without a recorded landslide are NOT confirmed non-events. They may represent unreported events, events in uninhabited areas, or events not captured by the reporting networks.

2. **Reporting bias**: Event points cluster near roads, towns, and tourist corridors. This creates a spatial bias that cannot be corrected by the ML model alone.

3. **Positional uncertainty**: Median accuracy of 5–10 km means event coordinates represent village/town administrative centers, not delineated failure scarp locations. Single-pixel extraction at these coordinates samples terrain features that may not correspond to the actual slope failure.

4. **No absence sampling performed**: The pipeline does NOT create synthetic negative/background examples. The Presence-Unlabeled (PU) / Presence-Background sampling strategy documented in the reconnaissance report (Section 12) is a Phase 2 task requiring explicit design decisions.

---

## 8. Soil Texture vs. Soil Moisture Demarcation

| Property | Soil Texture (Static) | Soil Moisture (Dynamic) |
|---|---|---|
| **Source** | ISRIC SoilGrids 250m | SMAP / GLEAM / GLDAS |
| **Parameters** | Clay %, Sand %, Silt % | Volumetric water content (m³/m³) |
| **Temporal variation** | None (composition is fixed) | Daily (varies with rainfall) |
| **Status** | Acquisition **not yet started** | Acquisition **not yet started** |
| **Pipeline role** | Static geotechnical proxy for drainability | Dynamic saturation indicator |
| **Claim restriction** | Labeled as "static texture proxy" | NOT claimed unless validated dynamic dataset acquired |

> [!WARNING]
> The pipeline does NOT claim that soil moisture is measured. Static soil texture and dynamic soil moisture are kept strictly separate in the data model and will remain so in all downstream analysis.

---

## 9. Recommendations for Phase 2

### 9.1 Completed Work (No Action Required)

- [x] All 11 DEM tiles acquired and verified
- [x] All 1,540 × 2 CHIRPS regional crops validated
- [x] 6 target district polygons verified
- [x] Feature pipeline code implemented and tested
- [x] 48 automated tests passing
- [x] Geospatial alignment audit completed with no issues

### 9.2 Recommendations (Phase 2 Actions)

| Priority | Recommendation | Rationale |
|---|---|---|
| **P1** | Implement multi-scale zonal buffer extraction (5–10 km) | Single-pixel extraction ignores 5–10 km positional uncertainty; zonal statistics (slope_p90, elev_relief, twi_p90) are required for defensible feature vectors |
| **P1** | Design and implement Presence-Background sampling | The PU learning framework requires background samples with spatial exclusion buffers and topographic domain stratification |
| **P2** | Acquire ISRIC SoilGrids 250m tiles (clay, sand, silt) | Static soil texture proxy is documented as a Phase 1 dependency but acquisition has not started |
| **P2** | Derive TWI from DEM (requires flow accumulation algorithm) | Topographic Wetness Index needs D-infinity or D8 flow routing — computationally intensive but no new data needed |
| **P2** | Compute aspect decomposition (sin/cos) and curvature | Currently only elevation and slope are extracted; aspect and curvature add geomorphic information |
| **P3** | Clean up 12 leftover `.tif.gz` files in rainfall directory | Minor disk space savings (~40 MB); no pipeline impact |
| **P3** | Evaluate dynamic soil moisture acquisition (GLEAM/SMAP) | Requires external account registration; bridges the gap between static texture and true saturation |

### 9.3 Blockers for Model Training

| Blocker | Severity | Resolution Path |
|---|:---:|---|
| **No negative/background samples** | **HIGH** | Must design and implement PU sampling before any classifier training |
| **Single-pixel extraction only** | **MEDIUM** | Zonal buffer aggregation should replace naive point extraction before training |
| **No soil features** | **LOW** | Model can be trained without soil initially; soil texture adds incremental value |

---

## 10. File Inventory

### Source Code
- [`src/features/raster_io.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/src/features/raster_io.py) — DEM and CHIRPS raster I/O (248 lines)
- [`src/features/feature_pipeline.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/src/features/feature_pipeline.py) — Feature extraction pipeline (395 lines)
- [`tests/test_feature_pipeline.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/tests/test_feature_pipeline.py) — 48 automated tests (1001 lines)

### Data Assets
- `data/raw/region_a/` — 8 DEM tiles + UGLC tile + sample CHIRPS
- `data/raw/region_b/` — 3 DEM tiles + 2 UGLC tiles
- `data/raw/rainfall/` — 3,080 CHIRPS regional crops
- `data/raw/boundaries/target_districts.geojson` — 6 district polygons

### Reports & Audit
- [`reports/data_reconnaissance_report.md`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/reports/data_reconnaissance_report.md) — Full M0 reconnaissance
- [`reports/feature_pipeline_readiness_report.md`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/reports/feature_pipeline_readiness_report.md) — This report
- [`scratch/geospatial_audit.py`](file:///c:/Users/VARMA/OneDrive/Desktop/AI project/scratch/geospatial_audit.py) — Geospatial alignment audit script

---

## 11. Summary Checklist

- [x] Inspected DEM tiles: CRS, geotransform, pixel size, nodata, dimensions verified
- [x] Inspected CHIRPS crops: CRS, origin, pixel size, nodata, dimensions verified
- [x] Inspected district GeoJSON: 6 polygons, bounding boxes verified
- [x] Inspected UGLC catalog: 3 tiles, 254 target events verified
- [x] Audited cross-raster alignment: WGS84 CRS match, 180:1 pixel ratio documented
- [x] Verified CHIRPS coverage: All 6 districts fully enclosed by regional crops
- [x] Verified DEM coverage: All 6 districts fully covered by 11 tiles
- [x] Identified DEM tile adjacency: Edge-sharing confirmed, no interior overlaps
- [x] Feature pipeline implemented: Elevation, slope, 3/7/15-day rainfall, spatial attribution
- [x] Automated tests written and passing: 48/48 tests across 9 categories
- [x] Soil texture/moisture demarcation documented
- [x] Presence-only limitations documented
- [x] No synthetic negatives created
- [x] No packages installed, no datasets downloaded, no models trained
- [x] Report saved to `reports/feature_pipeline_readiness_report.md`
