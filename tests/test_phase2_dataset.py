"""
tests/test_phase2_dataset.py
============================
Automated verification tests for Phase 2 Presence-Background dataset construction,
multi-scale DEM zonal features, spatial exclusion constraints, and temporal pairing.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.features.background_sampler import (
    DEFAULT_MIN_DIST_TO_BKG_KM,
    DEFAULT_MIN_DIST_TO_POS_KM,
    DISTRICT_QUOTAS,
    haversine_distance_km,
    sample_background_points,
)
from src.features.feature_pipeline import point_in_geometry

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def district_geoms():
    geojson_path = PROJECT_ROOT / "data" / "raw" / "boundaries" / "target_districts.geojson"
    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {feat["properties"]["target_district"]: feat["geometry"] for feat in data["features"]}


@pytest.fixture(scope="module")
def dataset_df():
    csv_path = PROJECT_ROOT / "data" / "processed" / "dataset_v1_features.csv"
    if not csv_path.exists():
        pytest.skip("dataset_v1_features.csv not yet generated")
    return pd.read_csv(csv_path)


class TestPrimaryPositiveInventory:

    def test_positive_count_and_unique_ids(self, dataset_df):
        positives = dataset_df[dataset_df["is_positive"] == 1]
        assert len(positives) == 144, f"Expected 144 positive events, got {len(positives)}"
        unique_ids = positives["event_id"].dropna().unique()
        assert len(unique_ids) == 144, f"Expected 144 unique event IDs, got {len(unique_ids)}"

    def test_positives_strictly_in_polygon(self, dataset_df, district_geoms):
        positives = dataset_df[dataset_df["is_positive"] == 1]
        for _, row in positives.iterrows():
            d = row["district"]
            assert d in district_geoms, f"Unknown district {d}"
            geom = district_geoms[d]
            assert point_in_geometry(float(row["lon"]), float(row["lat"]), geom), (
                f"Positive event {row['event_id']} not inside polygon of {d}"
            )


class TestBackgroundSamplingConstraints:

    def test_background_sample_count(self, dataset_df):
        background = dataset_df[dataset_df["is_positive"] == 0]
        assert len(background) == 432, f"Expected 432 background points, got {len(background)}"

    def test_district_quotas_satisfied(self, dataset_df):
        background = dataset_df[dataset_df["is_positive"] == 0]
        counts = background["district"].value_counts().to_dict()
        for d, expected_quota in DISTRICT_QUOTAS.items():
            assert counts.get(d, 0) == expected_quota, (
                f"District {d} expected {expected_quota} background samples, got {counts.get(d, 0)}"
            )

    def test_background_strictly_in_polygon(self, dataset_df, district_geoms):
        background = dataset_df[dataset_df["is_positive"] == 0]
        for _, row in background.iterrows():
            d = row["district"]
            geom = district_geoms[d]
            assert point_in_geometry(float(row["lon"]), float(row["lat"]), geom), (
                f"Background sample {row['sample_id']} not inside polygon of {d}"
            )

    def test_5km_exclusion_from_positives(self, dataset_df):
        positives = dataset_df[dataset_df["is_positive"] == 1]
        background = dataset_df[dataset_df["is_positive"] == 0]

        for d in DISTRICT_QUOTAS:
            d_pos = positives[positives["district"] == d]
            d_bkg = background[background["district"] == d]
            pos_coords = [(float(r["lon"]), float(r["lat"])) for _, r in d_pos.iterrows()]

            for _, b_row in d_bkg.iterrows():
                bx, by = float(b_row["lon"]), float(b_row["lat"])
                for px, py in pos_coords:
                    dist = haversine_distance_km(bx, by, px, py)
                    assert dist >= DEFAULT_MIN_DIST_TO_POS_KM - 1e-4, (
                        f"Background sample {b_row['sample_id']} is {dist:.3f} km from positive point, "
                        f"violating {DEFAULT_MIN_DIST_TO_POS_KM} km exclusion"
                    )

    def test_3km_inter_background_spacing(self, dataset_df):
        background = dataset_df[dataset_df["is_positive"] == 0]

        for d in DISTRICT_QUOTAS:
            d_bkg = background[background["district"] == d].copy()
            coords = [(float(r["lon"]), float(r["lat"]), r["sample_id"]) for _, r in d_bkg.iterrows()]

            for i in range(len(coords)):
                for j in range(i + 1, len(coords)):
                    lon1, lat1, id1 = coords[i]
                    lon2, lat2, id2 = coords[j]
                    dist = haversine_distance_km(lon1, lat1, lon2, lat2)
                    assert dist >= DEFAULT_MIN_DIST_TO_BKG_KM - 1e-4, (
                        f"Background points {id1} and {id2} in {d} are only {dist:.3f} km apart, "
                        f"violating {DEFAULT_MIN_DIST_TO_BKG_KM} km spacing"
                    )


class TestFeatureCompletenessAndMonotonicity:

    def test_zero_missing_values_across_features(self, dataset_df):
        feature_cols = [
            "elevation_m", "slope_deg",
            "rain_3d_mm", "rain_7d_mm", "rain_15d_mm",
            "slope_max_1km", "slope_p90_1km", "elev_relief_1km",
            "slope_max_3km", "slope_p90_3km", "elev_relief_3km",
            "slope_max_5km", "slope_p90_5km", "elev_relief_5km",
            "rain_3km_mean_3d", "rain_3km_mean_7d", "rain_3km_mean_15d",
        ]
        for col in feature_cols:
            n_null = dataset_df[col].isna().sum()
            assert n_null == 0, f"Feature column {col} has {n_null} missing values"

    def test_rainfall_window_monotonicity(self, dataset_df):
        # 3d <= 7d <= 15d for both point and 3km buffer
        assert (dataset_df["rain_3d_mm"] <= dataset_df["rain_7d_mm"] + 1e-4).all()
        assert (dataset_df["rain_7d_mm"] <= dataset_df["rain_15d_mm"] + 1e-4).all()

        assert (dataset_df["rain_3km_mean_3d"] <= dataset_df["rain_3km_mean_7d"] + 1e-4).all()
        assert (dataset_df["rain_3km_mean_7d"] <= dataset_df["rain_3km_mean_15d"] + 1e-4).all()

    def test_zonal_slope_consistency(self, dataset_df):
        # slope_max >= slope_p90 for all buffer scales
        for r in ["1km", "3km", "5km"]:
            assert (dataset_df[f"slope_max_{r}"] >= dataset_df[f"slope_p90_{r}"] - 1e-4).all(), (
                f"slope_max_{r} is smaller than slope_p90_{r}"
            )
            # relief >= 0
            assert (dataset_df[f"elev_relief_{r}"] >= 0).all()

    def test_sampler_deterministic_reproducibility(self, district_geoms):
        pos_records = [{"lon": 75.8, "lat": 11.5, "district": "Wayanad", "event_date": "2018-08-08"}]
        geojson_path = PROJECT_ROOT / "data" / "raw" / "boundaries" / "target_districts.geojson"
        rain_dir = PROJECT_ROOT / "data" / "raw" / "rainfall"

        pts1, _ = sample_background_points(geojson_path, pos_records, rain_dir, quotas={"Wayanad": 5}, seed=42)
        pts2, _ = sample_background_points(geojson_path, pos_records, rain_dir, quotas={"Wayanad": 5}, seed=42)

        for p1, p2 in zip(pts1, pts2):
            assert p1["lon"] == p2["lon"]
            assert p1["lat"] == p2["lat"]
            assert p1["event_date"] == p2["event_date"]
