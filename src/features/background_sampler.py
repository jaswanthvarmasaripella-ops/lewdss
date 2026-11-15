"""
src/features/background_sampler.py
==================================
Regional Landslide Risk & Emergency Response Decision System -- SIH26001
Phase 2: Presence-Background (PU) Sampler.

Implements spatial and temporal background sampling within official target district polygons.
Enforces:
  1. Strict polygon containment (via ray-casting point-in-geometry).
  2. Spatial exclusion zone: minimum 5.0 km distance from all known positive events.
  3. Spatial separation: minimum 3.0 km distance between generated background points.
  4. Date-paired co-occurrence: assigns dates from historical positive events in the same
     district/region with verified 15-day CHIRPS raster coverage.
  5. Deterministic reproducibility via seed (default: 42).

IMPORTANT METHODOLOGICAL LIMITATION:
-------------------------------------
Background points are UNLABELED samples (s = 0), NOT confirmed non-events (y = 0).
They represent the environmental and meteorological background of the study area during
historical monsoon periods under a formal Presence-Unlabeled (PU) framework.
"""

from __future__ import annotations

import datetime
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.features.feature_pipeline import (
    DISTRICT_REGION,
    REGION_SUFFIXES,
    _chirps_crop_path,
    point_in_geometry,
)

logger = logging.getLogger(__name__)

# Target quotas under Regional Quota Rebalancing (Decision 1, Option A)
DISTRICT_QUOTAS: Dict[str, int] = {
    "Kodagu": 27,
    "Idukki": 153,
    "Wayanad": 54,
    "East Sikkim": 28,
    "West Sikkim": 55,
    "East Khasi Hills": 115,
}

DEFAULT_MIN_DIST_TO_POS_KM: float = 5.0
DEFAULT_MIN_DIST_TO_BKG_KM: float = 3.0
DEFAULT_SEED: int = 42


def haversine_distance_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Great-circle distance between two WGS84 coordinates in kilometres.
    """
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return 6371.0 * c


def verify_chirps_15d_window(
    rainfall_dir: Path,
    event_date: str,
    region_suffix: str,
) -> bool:
    """
    Verify that all 15 daily CHIRPS regional crop files (t-14 to t) exist on disk.
    """
    d0 = datetime.date.fromisoformat(event_date.replace("/", "-"))
    for i in range(15):
        d = d0 - datetime.timedelta(days=14 - i)
        crop_path = _chirps_crop_path(rainfall_dir, d.isoformat(), region_suffix)
        if not crop_path.exists():
            return False
    return True


def sample_background_points(
    target_districts_geojson: Path | str,
    positive_events: List[Dict[str, Any]],
    rainfall_dir: Path | str,
    quotas: Dict[str, int] = DISTRICT_QUOTAS,
    min_dist_to_pos_km: float = DEFAULT_MIN_DIST_TO_POS_KM,
    min_dist_to_bkg_km: float = DEFAULT_MIN_DIST_TO_BKG_KM,
    seed: int = DEFAULT_SEED,
    max_attempts_per_sample: int = 2000,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Generate background samples across target districts adhering to all spatial
    exclusion and temporal co-occurrence constraints.

    Parameters
    ----------
    target_districts_geojson : Path to target_districts.geojson
    positive_events : List of verified in-polygon positive event dicts (must have lon, lat, district, event_date)
    rainfall_dir : Path to directory containing CHIRPS regional crop TIFFs
    quotas : District name -> target background count
    min_dist_to_pos_km : Minimum distance from any positive event (default: 5.0 km)
    min_dist_to_bkg_km : Minimum distance between background points (default: 3.0 km)
    seed : Random number generator seed (default: 42)
    max_attempts_per_sample : Max rejection iterations before declaring quota deficit

    Returns
    -------
    Tuple of:
      - List of background sample dicts
      - Audit summary dict (counts, deficits, constraints applied)
    """
    rainfall_dir = Path(rainfall_dir)
    geojson_path = Path(target_districts_geojson)

    with open(geojson_path, "r", encoding="utf-8") as f:
        dist_data = json.load(f)

    dist_geoms: Dict[str, dict] = {}
    for feat in dist_data["features"]:
        name = feat["properties"]["target_district"]
        dist_geoms[name] = feat["geometry"]

    rng = np.random.default_rng(seed)

    # Global coordinates of all positive events
    all_pos_coords = [(float(e["lon"]), float(e["lat"])) for e in positive_events]

    all_background_samples: List[Dict[str, Any]] = []
    district_audit: Dict[str, Any] = {}

    for district_name, target_count in quotas.items():
        if district_name not in dist_geoms:
            logger.warning("District %s not found in GeoJSON. Skipping.", district_name)
            continue

        geom = dist_geoms[district_name]
        region = DISTRICT_REGION.get(district_name, "")
        region_suffix = REGION_SUFFIXES.get(region, "")

        # Extract positive events for this district
        d_positives = [e for e in positive_events if e.get("district") == district_name]
        pos_dates = [e.get("event_date") or e.get("start_date") for e in d_positives]
        pos_dates = [d.replace("/", "-") for d in pos_dates if d]

        # If district has no positive dates (unlikely), fall back to regional dates
        if not pos_dates:
            reg_positives = [e for e in positive_events if DISTRICT_REGION.get(e.get("district")) == region]
            pos_dates = [e.get("event_date") or e.get("start_date") for e in reg_positives]
            pos_dates = [d.replace("/", "-") for d in pos_dates if d]

        # Extract bounding box from geometry coordinates
        coords: List[List[float]] = []

        def _flatten(c):
            for el in c:
                if isinstance(el[0], (int, float)):
                    yield el
                else:
                    yield from _flatten(el)

        coords = list(_flatten(geom["coordinates"]))
        lons = [p[0] for p in coords]
        lats = [p[1] for p in coords]
        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)

        district_samples: List[Dict[str, Any]] = []
        attempts = 0
        max_total_attempts = target_count * max_attempts_per_sample

        while len(district_samples) < target_count and attempts < max_total_attempts:
            attempts += 1
            cand_lon = float(rng.uniform(min_lon, max_lon))
            cand_lat = float(rng.uniform(min_lat, max_lat))

            # 1. Polygon containment
            if not point_in_geometry(cand_lon, cand_lat, geom):
                continue

            # 2. Global positive event exclusion buffer (>= 5 km from ALL 144 positives)
            too_close_pos = False
            for px, py in all_pos_coords:
                if haversine_distance_km(cand_lon, cand_lat, px, py) < min_dist_to_pos_km:
                    too_close_pos = True
                    break
            if too_close_pos:
                continue

            # 3. Global inter-background spacing (>= 3 km from ALL background points)
            too_close_bkg = False
            for bp in (all_background_samples + district_samples):
                if haversine_distance_km(cand_lon, cand_lat, bp["lon"], bp["lat"]) < min_dist_to_bkg_km:
                    too_close_bkg = True
                    break
            if too_close_bkg:
                continue

            # 4. Date-paired co-occurrence
            # Deterministically cycle through positive dates
            date_idx = len(district_samples) % len(pos_dates)
            paired_date = pos_dates[date_idx]

            # Verify 15-day CHIRPS window is present on disk
            if region_suffix and not verify_chirps_15d_window(rainfall_dir, paired_date, region_suffix):
                # Try finding an alternate valid positive date
                valid_found = False
                for alt_date in pos_dates:
                    if verify_chirps_15d_window(rainfall_dir, alt_date, region_suffix):
                        paired_date = alt_date
                        valid_found = True
                        break
                if not valid_found:
                    continue

            sample_idx = len(district_samples) + 1
            clean_dname = district_name.upper().replace(" ", "_")
            sample_id = f"BKG_{clean_dname}_{sample_idx:03d}"

            district_samples.append({
                "sample_id": sample_id,
                "is_positive": 0,
                "event_id": None,
                "event_date": paired_date,
                "lon": cand_lon,
                "lat": cand_lat,
                "district": district_name,
                "region": region,
                "match_type": "in_polygon",
                "paired_event_date": paired_date,
            })

        all_background_samples.extend(district_samples)
        deficit = target_count - len(district_samples)

        district_audit[district_name] = {
            "target_quota": target_count,
            "sampled_count": len(district_samples),
            "deficit": deficit,
            "attempts": attempts,
            "min_dist_to_pos_km": min_dist_to_pos_km,
            "min_dist_to_bkg_km": min_dist_to_bkg_km,
        }

        if deficit > 0:
            logger.warning(
                "District %s could not meet target quota (%d / %d sampled; deficit %d) "
                "without violating spatial constraints. Deficit preserved per AGENTS.md.",
                district_name,
                len(district_samples),
                target_count,
                deficit,
            )

    summary = {
        "total_target_quota": sum(quotas.values()),
        "total_sampled": len(all_background_samples),
        "total_deficit": sum(quotas.values()) - len(all_background_samples),
        "seed": seed,
        "min_dist_to_pos_km": min_dist_to_pos_km,
        "min_dist_to_bkg_km": min_dist_to_bkg_km,
        "district_breakdown": district_audit,
    }

    return all_background_samples, summary
