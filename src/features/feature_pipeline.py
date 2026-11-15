"""
src/features/feature_pipeline.py
================================
Regional Landslide Risk & Emergency Response Decision System -- SIH26001
Blueprint v2.0 * Milestone M1.4

Reproducible feature extraction pipeline.

This module extracts a structured feature table from:
  - UGLC audited landslide events (presence-only; see LIMITATIONS below)
  - Copernicus DEM 30m tiles → elevation, slope (Horn's 3×3)
  - CHIRPS 0.05° daily rainfall crops → 3-day, 7-day, 15-day accumulations

LIMITATIONS (as documented in the report)
------------------------------------------
1. The UGLC is a **presence-only** catalogue.  Dates and locations without
   a recorded landslide are *not* confirmed non-events — they are simply
   unrecorded.  This module does NOT create synthetic negative examples and
   does NOT treat unrecorded landslides as confirmed non-events.

2. Soil texture (e.g. USDA textural class from SoilGrids) is a static
   property and is kept separate from dynamic soil moisture.  This module
   does NOT claim that soil moisture is measured unless an appropriate
   dynamic dataset has been acquired and validated.

3. Some audited events are text-match or bbox-match only; their spatial
   attribution to a specific district may be approximate.  The ``match_type``
   column distinguishes in-polygon, in-bbox, and text-only matches.

Dependencies: numpy, pandas — both already installed.
"""

from __future__ import annotations

import datetime
import json
import logging
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.features.raster_io import (
    CHIRPS_CROP_NODATA,
    DEMIndex,
    DEMTile,
    chirps_buffer_mean_at,
    chirps_value_at,
    read_chirps_crop,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Region → CHIRPS filename suffix
REGION_SUFFIXES: Dict[str, str] = {
    "Region A (Western Ghats)": "_regionA.tif",
    "Region B (Northeast)": "_regionB.tif",
}

# District → region mapping
DISTRICT_REGION: Dict[str, str] = {
    "Wayanad": "Region A (Western Ghats)",
    "Idukki": "Region A (Western Ghats)",
    "Kodagu": "Region A (Western Ghats)",
    "East Sikkim": "Region B (Northeast)",
    "West Sikkim": "Region B (Northeast)",
    "East Khasi Hills": "Region B (Northeast)",
}

# Rainfall accumulation windows (days, inclusive of event day)
RAIN_WINDOWS: Tuple[int, ...] = (3, 7, 15)


# ---------------------------------------------------------------------------
# Point-in-polygon (pure Python, no shapely)
# ---------------------------------------------------------------------------

def _point_in_ring(x: float, y: float, ring: list) -> bool:
    """Ray-casting algorithm for a single polygon ring."""
    inside = False
    n = len(ring)
    p1x, p1y = ring[0]
    for i in range(1, n + 1):
        p2x, p2y = ring[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def point_in_geometry(x: float, y: float, geom: dict) -> bool:
    """Test if (lon, lat) falls inside a GeoJSON Polygon or MultiPolygon."""
    gtype = geom["type"]
    if gtype == "Polygon":
        exterior = geom["coordinates"][0]
        if not _point_in_ring(x, y, exterior):
            return False
        for hole in geom["coordinates"][1:]:
            if _point_in_ring(x, y, hole):
                return False
        return True
    elif gtype == "MultiPolygon":
        for poly in geom["coordinates"]:
            exterior = poly[0]
            if not _point_in_ring(x, y, exterior):
                continue
            in_hole = False
            for hole in poly[1:]:
                if _point_in_ring(x, y, hole):
                    in_hole = True
                    break
            if not in_hole:
                return True
        return False
    return False


# ---------------------------------------------------------------------------
# CHIRPS date-to-filename mapping
# ---------------------------------------------------------------------------

def _chirps_crop_path(
    rainfall_dir: Path,
    date_str: str,
    region_suffix: str,
) -> Path:
    """
    Build the path to a CHIRPS regional crop file.

    Example: rainfall_dir / "chirps-v2.0.2018.08.15_regionA.tif"
    """
    # date_str is "YYYY-MM-DD" or "YYYY/MM/DD"
    d = datetime.date.fromisoformat(date_str.replace("/", "-"))
    fname = f"chirps-v2.0.{d.year}.{d.month:02d}.{d.day:02d}{region_suffix}"
    return rainfall_dir / fname


# ---------------------------------------------------------------------------
# Rainfall accumulation
# ---------------------------------------------------------------------------

def compute_rainfall_accumulation(
    event_date: str,
    lon: float,
    lat: float,
    n_days: int,
    rainfall_dir: Path,
    region_suffix: str,
    radius_km: Optional[float] = None,
) -> Optional[float]:
    """
    Sum daily rainfall from (event_date − n_days + 1) to event_date inclusive.

    If radius_km is None: extracts point-sampled rainfall at (lon, lat).
    If radius_km is a float: extracts area-mean rainfall across CHIRPS cells within radius_km.

    Returns None if any date in the window is missing or the point is
    outside the crop extent for any date.
    """
    d0 = datetime.date.fromisoformat(event_date.replace("/", "-"))
    total = 0.0
    for i in range(n_days):
        d = d0 - datetime.timedelta(days=n_days - 1 - i)
        crop_path = _chirps_crop_path(rainfall_dir, d.isoformat(), region_suffix)
        if not crop_path.exists():
            logger.debug("Missing CHIRPS crop: %s", crop_path)
            return None
        arr, ox, oy, pdeg = read_chirps_crop(crop_path)
        if radius_km is not None and radius_km > 0:
            val = chirps_buffer_mean_at(arr, ox, oy, pdeg, lon, lat, radius_km=radius_km)
        else:
            val = chirps_value_at(arr, ox, oy, pdeg, lon, lat)
        if val is None:
            return None
        total += max(0.0, val)  # clamp sub-zero rainfall to 0
    return total


# ---------------------------------------------------------------------------
# Feature extraction for a single event or background sample
# ---------------------------------------------------------------------------

def extract_event_features(
    event: Dict[str, Any],
    dem_index: DEMIndex,
    rainfall_dir: Path,
    district_geoms: Dict[str, dict],
    district_bboxes: Dict[str, Tuple[float, float, float, float]],
) -> Dict[str, Any]:
    """
    Extract all features for a single audited event or background sample.

    Parameters
    ----------
    event : dict with keys lon, lat, district, and start_date/event_date.
            Optional keys: id, event_id, sample_id, is_positive.
    dem_index : DEMIndex with loaded tiles.
    rainfall_dir : Path to data/raw/rainfall/ containing crop TIFFs.
    district_geoms : district_name → GeoJSON geometry dict.
    district_bboxes : district_name → (min_lon, min_lat, max_lon, max_lat).

    Returns
    -------
    Feature dict with point features, multi-scale DEM zonal features,
    and 3 km buffer mean rainfall features.
    """
    lon, lat = float(event["lon"]), float(event["lat"])
    district = event.get("district", "")
    region = DISTRICT_REGION.get(district, "")
    region_suffix = REGION_SUFFIXES.get(region, "")

    raw_date = event.get("event_date") or event.get("start_date") or ""
    event_date = raw_date.replace("/", "-")

    # Sample ID & label
    sample_id = event.get("sample_id")
    raw_eid = event.get("id") or event.get("event_id")
    if not sample_id:
        sample_id = f"POS_{raw_eid}" if raw_eid else "UNKNOWN"
    is_positive = int(event.get("is_positive", 1 if raw_eid else 0))

    # --- Spatial attribution ---
    match_type = event.get("match_type")
    if not match_type or match_type == "unknown":
        if district in district_geoms:
            if point_in_geometry(lon, lat, district_geoms[district]):
                match_type = "in_polygon"
            elif district in district_bboxes:
                bb = district_bboxes[district]
                if bb[0] <= lon <= bb[2] and bb[1] <= lat <= bb[3]:
                    match_type = "in_bbox"
                else:
                    match_type = "text_only"
            else:
                match_type = "text_only"
        else:
            match_type = "text_only"

    # --- Point Terrain ---
    elevation = dem_index.elevation_at(lon, lat)
    slope = dem_index.slope_at(lon, lat)

    # --- Multi-Scale DEM Zonal Features (1 km, 3 km, 5 km) ---
    zonal_feats: Dict[str, Optional[float]] = {}
    for r_km in (1.0, 3.0, 5.0):
        tag = f"{int(r_km)}km"
        zs = dem_index.zonal_stats_at(lon, lat, r_km)
        zonal_feats[f"slope_max_{tag}"] = zs.get("slope_max")
        zonal_feats[f"slope_p90_{tag}"] = zs.get("slope_p90")
        zonal_feats[f"elev_relief_{tag}"] = zs.get("elev_relief")

    # --- Point Rainfall accumulations ---
    rain_feats: Dict[str, Optional[float]] = {}
    for w in RAIN_WINDOWS:
        if region_suffix and event_date:
            val = compute_rainfall_accumulation(
                event_date, lon, lat, w, rainfall_dir, region_suffix,
            )
        else:
            val = None
        rain_feats[f"rain_{w}d_mm"] = val

    # --- 3 km Areal Mean Rainfall accumulations ---
    rain_buffer_feats: Dict[str, Optional[float]] = {}
    for w in RAIN_WINDOWS:
        if region_suffix and event_date:
            val_bm = compute_rainfall_accumulation(
                event_date, lon, lat, w, rainfall_dir, region_suffix, radius_km=3.0,
            )
        else:
            val_bm = None
        rain_buffer_feats[f"rain_3km_mean_{w}d"] = val_bm

    return {
        "sample_id": sample_id,
        "is_positive": is_positive,
        "event_id": raw_eid,
        "event_date": event_date,
        "lon": lon,
        "lat": lat,
        "district": district,
        "region": region,
        "match_type": match_type,
        "elevation_m": elevation,
        "slope_deg": slope,
        **rain_feats,
        **zonal_feats,
        **rain_buffer_feats,
        "dem_available": elevation is not None,
        "rain_available": rain_feats.get("rain_15d_mm") is not None,
    }


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def build_feature_table(
    audited_events: List[Dict[str, Any]],
    dem_tile_paths: List[str | Path],
    rainfall_dir: str | Path,
    district_geojson_path: str | Path,
) -> pd.DataFrame:
    """
    Build the complete feature table from audited events or background samples.

    Parameters
    ----------
    audited_events : list of dicts with lon, lat, district, and start_date/event_date.
    dem_tile_paths : list of paths to Copernicus DEM .tif files.
    rainfall_dir   : path to directory containing CHIRPS crop .tif files.
    district_geojson_path : path to target_districts.geojson.

    Returns
    -------
    pd.DataFrame with one row per sample, columns per extracted feature.
    """
    import json as _json

    rainfall_dir = Path(rainfall_dir)
    district_geojson_path = Path(district_geojson_path)

    # Load district geometries
    with open(district_geojson_path, "r", encoding="utf-8") as f:
        dist_data = _json.load(f)

    district_geoms: Dict[str, dict] = {}
    district_bboxes: Dict[str, Tuple[float, float, float, float]] = {}
    for feat in dist_data["features"]:
        name = feat["properties"]["target_district"]
        district_geoms[name] = feat["geometry"]

        def _flatten(coords):
            for el in coords:
                if isinstance(el[0], (int, float)):
                    yield el
                else:
                    yield from _flatten(el)

        pts = list(_flatten(feat["geometry"]["coordinates"]))
        lons = [p[0] for p in pts]
        lats = [p[1] for p in pts]
        district_bboxes[name] = (min(lons), min(lats), max(lons), max(lats))

    # Load DEM tiles
    logger.info("Loading %d DEM tiles...", len(dem_tile_paths))
    dem_index = DEMIndex(dem_tile_paths)
    logger.info("DEM tiles loaded.")

    # Extract features
    rows: List[Dict[str, Any]] = []
    for i, ev in enumerate(audited_events):
        row = extract_event_features(
            ev, dem_index, rainfall_dir, district_geoms, district_bboxes,
        )
        rows.append(row)
        if (i + 1) % 50 == 0:
            logger.info("Extracted features for %d / %d samples", i + 1, len(audited_events))

    df = pd.DataFrame(rows)

    # Standardized column ordering
    col_order = [
        "sample_id", "is_positive", "event_id", "event_date", "lon", "lat",
        "district", "region", "match_type",
        # Point features
        "elevation_m", "slope_deg",
        "rain_3d_mm", "rain_7d_mm", "rain_15d_mm",
        # Multi-scale DEM zonal features
        "slope_max_1km", "slope_p90_1km", "elev_relief_1km",
        "slope_max_3km", "slope_p90_3km", "elev_relief_3km",
        "slope_max_5km", "slope_p90_5km", "elev_relief_5km",
        # 3 km buffer rainfall features
        "rain_3km_mean_3d", "rain_3km_mean_7d", "rain_3km_mean_15d",
        # Flags
        "dem_available", "rain_available",
    ]
    df = df[[c for c in col_order if c in df.columns]]

    return df


def validate_feature_table(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Run validation checks on the feature table.

    Returns a dict with check results and summary statistics.
    """
    n = len(df)
    checks: Dict[str, Any] = {
        "total_events": n,
        "dem_coverage": int(df["dem_available"].sum()) if "dem_available" in df else 0,
        "dem_coverage_pct": float(df["dem_available"].mean() * 100) if "dem_available" in df else 0.0,
        "rain_coverage": int(df["rain_available"].sum()) if "rain_available" in df else 0,
        "rain_coverage_pct": float(df["rain_available"].mean() * 100) if "rain_available" in df else 0.0,
    }

    # Elevation range
    elev = df["elevation_m"].dropna()
    if len(elev) > 0:
        checks["elevation_min"] = float(elev.min())
        checks["elevation_max"] = float(elev.max())
        checks["elevation_mean"] = float(elev.mean())
        # Sanity: no events should be below sea level by > 50m
        checks["elevation_below_neg50"] = int((elev < -50).sum())

    # Slope range
    slope = df["slope_deg"].dropna()
    if len(slope) > 0:
        checks["slope_min"] = float(slope.min())
        checks["slope_max"] = float(slope.max())
        checks["slope_mean"] = float(slope.mean())
        # Sanity: slopes > 85° are implausible for terrain
        checks["slope_above_85"] = int((slope > 85).sum())

    # Rainfall sanity
    for w in RAIN_WINDOWS:
        col = f"rain_{w}d_mm"
        if col in df:
            rain = df[col].dropna()
            if len(rain) > 0:
                checks[f"rain_{w}d_min"] = float(rain.min())
                checks[f"rain_{w}d_max"] = float(rain.max())
                checks[f"rain_{w}d_mean"] = float(rain.mean())
                # Negative rainfall should not exist after clamping
                checks[f"rain_{w}d_negative"] = int((rain < 0).sum())

    # Match type distribution
    if "match_type" in df:
        checks["match_type_counts"] = df["match_type"].value_counts().to_dict()

    # District distribution
    if "district" in df:
        checks["district_counts"] = df["district"].value_counts().to_dict()

    return checks
