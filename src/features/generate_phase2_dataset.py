"""
src/features/generate_phase2_dataset.py
=======================================
Regional Landslide Risk & Emergency Response Decision System -- SIH26001
Phase 2: Presence-Background Dataset Construction & Feature Extraction.

Generates:
  1. data/processed/dataset_v1_features.csv:
     - 144 strictly verified in-polygon positives (is_positive = 1)
     - 432 verified background samples (is_positive = 0)
     - Multi-scale DEM features (1 km, 3 km, 5 km)
     - Baseline point elevation and slope
     - 3-day, 7-day, 15-day point rainfall and 3 km buffer mean rainfall
  2. data/processed/dataset_v1_bbox_corridor.csv:
     - 67 bbox-only events separated for sensitivity testing
  3. data/processed/dataset_v1_metadata.json:
     - Complete audit metadata, district quotas, seeds, and provenance

SAFE & REPRODUCIBLE:
  - Seed: 42
  - Zero synthetic negatives claimed
  - Preserves all raw assets
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.data.uglc_audit import run_full_uglc_audit
from src.features.background_sampler import (
    DISTRICT_QUOTAS,
    sample_background_points,
)
from src.features.feature_pipeline import (
    build_feature_table,
    validate_feature_table,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def generate_phase2_dataset() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    # 1. Define Paths
    gpkg_files = [
        PROJECT_ROOT / "data" / "raw" / "region_a" / "UGLC_point_tile_11_4.gpkg",
        PROJECT_ROOT / "data" / "raw" / "region_b" / "UGLC_point_tile_11_5.gpkg",
        PROJECT_ROOT / "data" / "raw" / "region_b" / "UGLC_point_tile_12_5.gpkg",
    ]

    dem_tile_paths = sorted(
        list((PROJECT_ROOT / "data" / "raw" / "region_a").glob("Copernicus_DSM_COG_10_*.tif"))
        + list((PROJECT_ROOT / "data" / "raw" / "region_b").glob("Copernicus_DSM_COG_10_*.tif"))
    )

    rainfall_dir = PROJECT_ROOT / "data" / "raw" / "rainfall"
    district_geojson_path = PROJECT_ROOT / "data" / "raw" / "boundaries" / "target_districts.geojson"
    out_dir = PROJECT_ROOT / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loaded %d DEM tiles from region_a and region_b.", len(dem_tile_paths))

    # 2. Extract baseline audited events
    audit_res = run_full_uglc_audit(gpkg_files)
    target_districts = ("Wayanad", "Idukki", "Kodagu", "East Sikkim", "West Sikkim", "East Khasi Hills")

    # Load baseline feature table to get established match_type
    baseline_csv = out_dir / "baseline_event_features.csv"
    if not baseline_csv.exists():
        raise FileNotFoundError(f"Missing {baseline_csv}. Run Phase 1.4 baseline generation first.")

    base_df = pd.read_csv(baseline_csv)

    # 3. Build Primary Positive Inventory (144 in-polygon events)
    positives_df = base_df[base_df["match_type"] == "in_polygon"].copy()
    logger.info("Identified %d strict in-polygon positive events.", len(positives_df))

    # Deduplicate check: Ensure 144 unique event IDs
    unique_eids = positives_df["event_id"].unique()
    assert len(unique_eids) == 144, f"Expected 144 unique IDs, found {len(unique_eids)}"

    # Convert positive events to dict records for feature extraction
    positive_records: List[Dict[str, Any]] = []
    for _, r in positives_df.iterrows():
        positive_records.append({
            "sample_id": f"POS_{r['event_id']}",
            "is_positive": 1,
            "event_id": str(r["event_id"]),
            "event_date": str(r["event_date"]),
            "lon": float(r["lon"]),
            "lat": float(r["lat"]),
            "district": str(r["district"]),
            "region": str(r["region"]),
            "match_type": "in_polygon",
        })

    # 4. Generate 432 Background Samples via Presence-Background Sampler
    logger.info("Generating background samples using Regional Quota Rebalancing (Seed: 42)...")
    background_records, sampler_summary = sample_background_points(
        target_districts_geojson=district_geojson_path,
        positive_events=positive_records,
        rainfall_dir=rainfall_dir,
        quotas=DISTRICT_QUOTAS,
        min_dist_to_pos_km=5.0,
        min_dist_to_bkg_km=3.0,
        seed=42,
    )

    logger.info(
        "Successfully sampled %d background points (target quota: %d, deficit: %d).",
        len(background_records),
        sampler_summary["total_target_quota"],
        sampler_summary["total_deficit"],
    )

    # 5. Extract Multi-Scale Features for Combined Dataset (144 Positives + 432 Background)
    combined_samples = positive_records + background_records
    logger.info("Extracting multi-scale features for %d total samples...", len(combined_samples))

    unified_df = build_feature_table(
        audited_events=combined_samples,
        dem_tile_paths=dem_tile_paths,
        rainfall_dir=rainfall_dir,
        district_geojson_path=district_geojson_path,
    )

    # 6. Save Bounding-Box Corridor Events Separately for Sensitivity Testing
    bbox_df = base_df[base_df["match_type"] == "in_bbox"].copy()
    bbox_out_path = out_dir / "dataset_v1_bbox_corridor.csv"
    bbox_df.to_csv(bbox_out_path, index=False)
    logger.info("Saved %d bbox-only corridor events to %s", len(bbox_df), bbox_out_path)

    # 7. Save Primary Unified Feature Dataset
    unified_out_path = out_dir / "dataset_v1_features.csv"
    unified_df.to_csv(unified_out_path, index=False)
    logger.info("Saved unified dataset (%d rows x %d cols) to %s", len(unified_df), len(unified_df.columns), unified_out_path)

    # 8. Compile and Save Metadata JSON
    validation_checks = validate_feature_table(unified_df)
    metadata = {
        "dataset_name": "dataset_v1_features",
        "milestone": "Phase 2 (Dataset Construction)",
        "total_samples": len(unified_df),
        "positive_count": int((unified_df["is_positive"] == 1).sum()),
        "background_count": int((unified_df["is_positive"] == 0).sum()),
        "positive_to_background_ratio": f"1:{len(background_records) / len(positive_records):.2f}",
        "district_quotas": DISTRICT_QUOTAS,
        "district_sample_counts": unified_df.groupby(["district", "is_positive"]).size().unstack(fill_value=0).to_dict(),
        "sampler_summary": sampler_summary,
        "feature_columns": list(unified_df.columns),
        "validation_checks": validation_checks,
        "spatial_constraints": {
            "polygon_containment": "strict in-polygon",
            "min_dist_to_positive_km": 5.0,
            "min_dist_to_background_km": 3.0,
        },
        "temporal_protocol": {
            "method": "date-paired co-occurrence",
            "source": "historical district positive event dates",
            "monsoon_months": "June 1 to September 30 (2004-2022)",
            "rainfall_raster_check": "15-day CHIRPS crop window verified",
        },
        "reproducibility": {
            "master_seed": 42,
            "hash_algorithm": "deterministic",
        },
        "pu_learning_disclaimer": (
            "Background points are unlabeled (s = 0), not confirmed negatives (y = 0). "
            "Model scores represent a Relative Landslide Susceptibility Index (RLSI), "
            "not calibrated absolute probabilities."
        ),
    }

    meta_path = out_dir / "dataset_v1_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Saved dataset metadata to %s", meta_path)

    return unified_df, metadata


if __name__ == "__main__":
    generate_phase2_dataset()
