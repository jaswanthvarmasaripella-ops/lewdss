"""
src/data/validation.py
======================
Regional Landslide Risk & Emergency Response Decision System -- SIH26001
Blueprint v2.0 * Milestone M0

Data quality checks implementing all 12 checks defined in Section 18 of
Blueprint v2.0.

IMPORTANT
---------
This module contains two categories of checks:

  CATEGORY A -- Schema / structural checks (can run without downloaded data)
    These validate that a DataFrame passed to them meets structural requirements.
    They are runnable in the M0 test suite with synthetic or mock data.

  CATEGORY B -- Data-content checks (require downloaded files)
    These read rasters, shapefiles, or event CSVs and cannot pass until real
    data exists. They are defined here so the scaffold is complete, but their
    pytest tests are marked @pytest.mark.needs_data and are skipped by default.

Usage
-----
    from src.data.validation import run_all_checks, DataQualityReport

    report = run_all_checks(df, config)
    report.print_summary()
    report.raise_on_failure()   # raises DataQualityError if any check failed

Each individual check is also callable:

    from src.data.validation import check_schema, check_null_fraction
    result = check_schema(df, expected_columns)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DataQualityError(RuntimeError):
    """Raised when one or more mandatory data quality checks fail."""


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """Outcome of a single data quality check."""
    check_id: int
    name: str
    category: str          # "A" = no-data-required | "B" = needs_downloaded_data
    status: str            # "PASS" | "FAIL" | "WARN" | "SKIP"
    detail: str            # Human-readable description of outcome
    mandatory: bool = True  # If True, FAIL triggers DataQualityError


@dataclass
class DataQualityReport:
    """Collects results from all 12 checks."""
    results: list[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.results.append(result)
        level = logging.WARNING if result.status in ("FAIL", "WARN") else logging.INFO
        logger.log(level, "[Check %02d | %s | %s] %s -- %s",
                   result.check_id, result.category, result.status,
                   result.name, result.detail)

    def print_summary(self) -> None:
        print("\n" + "=" * 72)
        print("DATA QUALITY REPORT - LEWDSS (Blueprint v2.0)")
        print("=" * 72)
        for r in self.results:
            icon = {"PASS": "[OK]  ", "FAIL": "[FAIL]", "WARN": "[WARN]", "SKIP": "[SKIP]"}.get(r.status, "[?]  ")
            print(f"  {icon} Check {r.check_id:02d} [{r.category}] {r.status:<4}  {r.name}")
            print(f"         {r.detail}")
        passed  = sum(1 for r in self.results if r.status == "PASS")
        failed  = sum(1 for r in self.results if r.status == "FAIL")
        warned  = sum(1 for r in self.results if r.status == "WARN")
        skipped = sum(1 for r in self.results if r.status == "SKIP")
        print("-" * 72)
        print(f"  PASS: {passed}  FAIL: {failed}  WARN: {warned}  SKIP: {skipped}")
        print("=" * 72 + "\n")

    def raise_on_failure(self) -> None:
        failures = [r for r in self.results if r.status == "FAIL" and r.mandatory]
        if failures:
            names = ", ".join(r.name for r in failures)
            raise DataQualityError(
                f"{len(failures)} mandatory check(s) failed: {names}. "
                "See DataQualityReport for details."
            )

    @property
    def all_passed(self) -> bool:
        return all(r.status in ("PASS", "WARN", "SKIP") for r in self.results)


# =============================================================================
# CATEGORY A -- Schema / structural checks (no downloaded data required)
# =============================================================================

def check_01_schema(
    df: pd.DataFrame,
    expected_columns: list[str],
) -> CheckResult:
    """
    Check 1 -- Schema check (Category A)
    All expected columns must be present in the DataFrame after merge.
    """
    missing = [c for c in expected_columns if c not in df.columns]
    if missing:
        return CheckResult(
            check_id=1, name="Schema check", category="A",
            status="FAIL",
            detail=f"Missing columns: {missing}",
        )
    return CheckResult(
        check_id=1, name="Schema check", category="A",
        status="PASS",
        detail=f"All {len(expected_columns)} expected columns present.",
    )


def check_02_crs(
    crs_set: set[str],
    target_crs: str = "EPSG:4326",
) -> CheckResult:
    """
    Check 2 -- CRS consistency check (Category A / B hybrid)
    All loaded spatial layers must share the same CRS before merging.

    Parameters
    ----------
    crs_set : set[str]
        Set of CRS strings found across all loaded spatial layers.
    target_crs : str
        Expected CRS (from config).

    NOTE: When no spatial files are loaded yet (M0), pass an empty set.
          The check will return SKIP.
    """
    if not crs_set:
        return CheckResult(
            check_id=2, name="CRS consistency check", category="B",
            status="SKIP",
            detail="No spatial files loaded yet -- check will run in Phase 1.",
            mandatory=False,
        )
    unexpected = crs_set - {target_crs}
    if unexpected:
        return CheckResult(
            check_id=2, name="CRS consistency check", category="B",
            status="FAIL",
            detail=f"Non-target CRS found: {unexpected}. Expected: {target_crs}",
        )
    return CheckResult(
        check_id=2, name="CRS consistency check", category="B",
        status="PASS",
        detail=f"All spatial layers in {target_crs}.",
    )


def check_03_null_fraction(
    df: pd.DataFrame,
    max_missing: float = 0.20,
    columns: list[str] | None = None,
) -> CheckResult:
    """
    Check 3 -- Null fraction check (Category A)
    Column-wise null fraction computed and logged; fail if any column exceeds threshold.
    If `columns` is specified, checks only those columns.
    """
    target_df = df[columns] if columns is not None else df
    null_fractions = target_df.isnull().mean()
    over_threshold = null_fractions[null_fractions > max_missing]
    if not over_threshold.empty:
        detail = "; ".join(
            f"{col}: {frac:.1%}" for col, frac in over_threshold.items()
        )
        return CheckResult(
            check_id=3, name="Null fraction check", category="A",
            status="FAIL",
            detail=f"Columns exceed {max_missing:.0%} missing threshold: {detail}",
        )
    max_observed = null_fractions.max() if len(null_fractions) > 0 else 0.0
    return CheckResult(
        check_id=3, name="Null fraction check", category="A",
        status="PASS",
        detail=f"Max null fraction: {max_observed:.1%} (threshold: {max_missing:.0%})",
    )


def check_04_value_ranges(df: pd.DataFrame) -> CheckResult:
    """
    Check 4 -- Value range check (Category A)
    Validates physical plausibility of terrain and rainfall features.

    Expected columns (skipped gracefully if absent):
      slope_deg       : 0-90  (flag > 85 deg as likely DEM artifact)
      rain_7d_mm      : 0-2000
      sm_obs          : 0-1   (volumetric water content m3/m3)
      soil_clay_pct   : 0-100
      elevation_m     : > -500
    """
    checks = {
        "slope_deg":    (0, 90,   True),   # (min, max, strict_upper)
        "rain_7d_mm":   (0, 2000, False),
        "sm_obs":       (0, 1,    True),
        "soil_clay_pct":(0, 100,  True),
        "elevation_m":  (-500, None, False),
    }
    violations: list[str] = []
    warnings:   list[str] = []

    for col, (lo, hi, strict) in checks.items():
        if col not in df.columns:
            continue
        series = df[col].dropna()
        if lo is not None and (series < lo).any():
            violations.append(f"{col} has values < {lo}")
        if hi is not None:
            if strict and (series > hi).any():
                violations.append(f"{col} has values > {hi}")
            elif not strict and (series > hi).any():
                warnings.append(f"{col} has values > {hi} (review manually)")
        # Special: flag slope > 85 deg as DEM artifact
        if col == "slope_deg" and (series > 85).any():
            warnings.append(
                f"slope_deg: {(series > 85).sum()} values > 85 deg -- likely DEM artifact"
            )

    if violations:
        return CheckResult(
            check_id=4, name="Value range check", category="A",
            status="FAIL",
            detail="; ".join(violations),
        )
    if warnings:
        return CheckResult(
            check_id=4, name="Value range check", category="A",
            status="WARN",
            detail="; ".join(warnings),
            mandatory=False,
        )
    return CheckResult(
        check_id=4, name="Value range check", category="A",
        status="PASS",
        detail="All present feature columns within expected physical ranges.",
    )


def check_05_duplicates(df: pd.DataFrame) -> CheckResult:
    """
    Check 5 -- Duplicate (district_id, date) check (Category A)
    Each (district_id, date) pair must appear at most once.
    """
    key_cols = [c for c in ("district_id", "date") if c in df.columns]
    if len(key_cols) < 2:
        return CheckResult(
            check_id=5, name="Duplicate key check", category="A",
            status="SKIP",
            detail="Columns 'district_id' and/or 'date' not present -- skipped.",
            mandatory=False,
        )
    n_dupes = df.duplicated(subset=key_cols).sum()
    if n_dupes > 0:
        return CheckResult(
            check_id=5, name="Duplicate key check", category="A",
            status="FAIL",
            detail=f"{n_dupes} duplicate (district_id, date) rows found.",
        )
    return CheckResult(
        check_id=5, name="Duplicate key check", category="A",
        status="PASS",
        detail=f"No duplicate (district_id, date) rows. Total rows: {len(df)}",
    )


def check_06_spatial_bounds(
    df: pd.DataFrame,
    bbox: dict[str, float],
) -> CheckResult:
    """
    Check 6 -- Spatial bounds check (Category A)
    All district centroid coordinates must fall within the declared region bounding box.

    Parameters
    ----------
    bbox : dict with keys min_lon, max_lon, min_lat, max_lat
    """
    required = {"centroid_lon", "centroid_lat"}
    if not required.issubset(df.columns):
        return CheckResult(
            check_id=6, name="Spatial bounds check", category="A",
            status="SKIP",
            detail="centroid_lon / centroid_lat not present -- skipped.",
            mandatory=False,
        )
    out_lon = ~df["centroid_lon"].between(bbox["min_lon"], bbox["max_lon"])
    out_lat = ~df["centroid_lat"].between(bbox["min_lat"], bbox["max_lat"])
    out_of_bounds = (out_lon | out_lat).sum()
    if out_of_bounds > 0:
        return CheckResult(
            check_id=6, name="Spatial bounds check", category="A",
            status="FAIL",
            detail=f"{out_of_bounds} district centroids outside declared bounding box.",
        )
    return CheckResult(
        check_id=6, name="Spatial bounds check", category="A",
        status="PASS",
        detail=f"All {len(df)} centroids within bounding box.",
    )


def check_07_catalog_crosswalk(df: pd.DataFrame) -> CheckResult:
    """
    Check 7 -- Event catalog crosswalk (Category A / B)
    Every row with target=1 must have at least one non-null catalog source logged.
    Expects a 'catalog_source' column created during preprocessing.
    """
    if "catalog_source" not in df.columns:
        return CheckResult(
            check_id=7, name="Catalog crosswalk check", category="B",
            status="SKIP",
            detail="'catalog_source' column not present -- skipped until Phase 1.",
            mandatory=False,
        )
    if "target" not in df.columns:
        return CheckResult(
            check_id=7, name="Catalog crosswalk check", category="B",
            status="SKIP",
            detail="'target' column not present -- skipped.",
            mandatory=False,
        )
    events = df[df["target"] == 1]
    unsourced = events["catalog_source"].isnull().sum()
    if unsourced > 0:
        return CheckResult(
            check_id=7, name="Catalog crosswalk check", category="B",
            status="FAIL",
            detail=f"{unsourced} event rows (target=1) have no catalog source.",
        )
    return CheckResult(
        check_id=7, name="Catalog crosswalk check", category="B",
        status="PASS",
        detail=f"All {len(events)} event rows linked to >= 1 catalog source.",
    )


def check_08_date_precision(df: pd.DataFrame, min_fraction: float = 0.80) -> CheckResult:
    """
    Check 8 -- Event date precision (Category A / B)
    At least `min_fraction` of event rows must have day-level date precision.
    Expects a 'date_precision' column with values: 'day', 'month', 'year', or NaN.
    """
    if "date_precision" not in df.columns:
        return CheckResult(
            check_id=8, name="Date precision check", category="B",
            status="SKIP",
            detail="'date_precision' column not present -- will be populated in Phase 1.",
            mandatory=False,
        )
    if "target" not in df.columns:
        return CheckResult(
            check_id=8, name="Date precision check", category="B",
            status="SKIP",
            detail="'target' column not present -- skipped.",
            mandatory=False,
        )
    events = df[df["target"] == 1]
    if len(events) == 0:
        return CheckResult(
            check_id=8, name="Date precision check", category="B",
            status="SKIP", detail="No event rows (target=1) found.", mandatory=False,
        )
    day_fraction = (events["date_precision"] == "day").sum() / len(events)
    if day_fraction < min_fraction:
        return CheckResult(
            check_id=8, name="Date precision check", category="B",
            status="FAIL",
            detail=(
                f"Only {day_fraction:.1%} of events have day-level date precision "
                f"(minimum required: {min_fraction:.0%}). "
                "Task may need to be reframed as susceptibility mapping."
            ),
        )
    return CheckResult(
        check_id=8, name="Date precision check", category="B",
        status="PASS",
        detail=f"{day_fraction:.1%} of events have day-level date precision.",
    )


def check_09_class_imbalance(
    df: pd.DataFrame,
    min_ratio: float = 0.5,   # positive / negative >= 0.5 (1:2)
    max_ratio: float = 15.0,  # positive / negative <= 15 (1:15 of negatives)
) -> CheckResult:
    """
    Check 9 -- Class imbalance report (Category A)
    Log the positive:negative ratio. Flag if outside acceptable range.
    The ratio is: n_negatives / n_positives (so "1:3" means ratio = 3.0).
    """
    if "target" not in df.columns:
        return CheckResult(
            check_id=9, name="Class imbalance check", category="A",
            status="SKIP",
            detail="'target' column not present -- skipped.",
            mandatory=False,
        )
    n_pos = (df["target"] == 1).sum()
    n_neg = (df["target"] == 0).sum()
    if n_pos == 0:
        return CheckResult(
            check_id=9, name="Class imbalance check", category="A",
            status="FAIL",
            detail="Zero positive (event) samples found.",
        )
    ratio = n_neg / n_pos  # e.g., 3.0 means 1:3 pos:neg
    detail = f"n_positive={n_pos}, n_negative={n_neg}, ratio (neg/pos)={ratio:.2f}"
    if ratio < min_ratio:
        return CheckResult(
            check_id=9, name="Class imbalance check", category="A",
            status="WARN",
            detail=f"Ratio {ratio:.2f} < {min_ratio} -- too many positives relative to negatives. {detail}",
            mandatory=False,
        )
    if ratio > max_ratio:
        return CheckResult(
            check_id=9, name="Class imbalance check", category="A",
            status="WARN",
            detail=f"Ratio {ratio:.2f} > {max_ratio} -- severe imbalance. {detail}",
            mandatory=False,
        )
    return CheckResult(
        check_id=9, name="Class imbalance check", category="A",
        status="PASS",
        detail=detail,
    )


def check_10_temporal_coverage(
    df: pd.DataFrame,
    min_antecedent_days: int = 15,
) -> CheckResult:
    """
    Check 10 -- Temporal coverage check (Category A / B)
    For every event row (target=1), the dataset must contain rainfall and soil
    moisture observations for at least `min_antecedent_days` before the event date.

    In practice this is verified by checking that `rain_15d_mm` (and/or SM columns)
    are non-null for all event rows -- these features require 15 days of prior data.
    """
    if "target" not in df.columns:
        return CheckResult(
            check_id=10, name="Temporal coverage check", category="B",
            status="SKIP",
            detail="'target' column not present -- skipped.",
            mandatory=False,
        )
    # Check which antecedent features exist
    antecedent_cols = [c for c in ("rain_15d_mm", "rain_7d_mm", "sm_3d_mean") if c in df.columns]
    if not antecedent_cols:
        return CheckResult(
            check_id=10, name="Temporal coverage check", category="B",
            status="SKIP",
            detail="Antecedent rainfall/SM columns not present -- will run in Phase 2.",
            mandatory=False,
        )
    events = df[df["target"] == 1]
    missing_antecedent = events[antecedent_cols].isnull().any(axis=1).sum()
    if missing_antecedent > 0:
        return CheckResult(
            check_id=10, name="Temporal coverage check", category="B",
            status="FAIL",
            detail=(
                f"{missing_antecedent} event rows have null antecedent features "
                f"({antecedent_cols}). Rainfall data does not span >= {min_antecedent_days} "
                "days before those events."
            ),
        )
    return CheckResult(
        check_id=10, name="Temporal coverage check", category="B",
        status="PASS",
        detail=f"All event rows have non-null antecedent features for >= {min_antecedent_days} days.",
    )


def check_11_dem_voids(df: pd.DataFrame, nodata_value: float = -9999.0) -> CheckResult:
    """
    Check 11 -- DEM void / NoData check (Category A / B)
    Flag rows where elevation_m equals the NoData sentinel value.
    """
    if "elevation_m" not in df.columns:
        return CheckResult(
            check_id=11, name="DEM void check", category="B",
            status="SKIP",
            detail="'elevation_m' column not present -- will run after DEM extraction.",
            mandatory=False,
        )
    void_rows = (df["elevation_m"] == nodata_value).sum()
    nan_rows  = df["elevation_m"].isnull().sum()
    if void_rows > 0 or nan_rows > 0:
        return CheckResult(
            check_id=11, name="DEM void check", category="B",
            status="FAIL" if void_rows > 0 else "WARN",
            detail=f"DEM NoData rows: {void_rows} (sentinel={nodata_value}), NaN rows: {nan_rows}",
            mandatory=(void_rows > 0),
        )
    return CheckResult(
        check_id=11, name="DEM void check", category="B",
        status="PASS",
        detail=f"No DEM void / NoData values found in {len(df)} rows.",
    )


def check_12_sm_tier_consistency(df: pd.DataFrame) -> CheckResult:
    """
    Check 12 -- Soil moisture tier flag consistency (Category A)
    The `sm_tier` column must be present and contain only values in {1, 2, 3}.
    This check is runnable as soon as the feature DataFrame is assembled.
    """
    if "sm_tier" not in df.columns:
        return CheckResult(
            check_id=12, name="SM tier consistency check", category="A",
            status="SKIP",
            detail="'sm_tier' column not present -- will be added in Phase 2 feature assembly.",
            mandatory=False,
        )
    valid = {1, 2, 3}
    invalid_vals = set(df["sm_tier"].dropna().unique()) - valid
    null_count   = df["sm_tier"].isnull().sum()
    if invalid_vals or null_count > 0:
        return CheckResult(
            check_id=12, name="SM tier consistency check", category="A",
            status="FAIL",
            detail=(
                f"Invalid sm_tier values: {invalid_vals}. "
                f"Null sm_tier rows: {null_count}. "
                "Valid values are {{1, 2, 3}}."
            ),
        )
    tier_counts = df["sm_tier"].value_counts().to_dict()
    return CheckResult(
        check_id=12, name="SM tier consistency check", category="A",
        status="PASS",
        detail=f"All sm_tier values in {{1,2,3}}. Distribution: {tier_counts}",
    )


# =============================================================================
# Orchestrator -- run all 12 checks
# =============================================================================

def run_all_checks(
    df: pd.DataFrame,
    config: dict[str, Any],
    crs_set: set[str] | None = None,
    region_code: str | None = None,
) -> DataQualityReport:
    """
    Run all 12 data quality checks defined in Blueprint v2.0 Section 18.

    Parameters
    ----------
    df          : The assembled feature DataFrame (may be partial in early phases)
    config      : Loaded config.yaml as dict (via yaml.safe_load)
    crs_set     : Set of CRS strings from loaded spatial layers (pass None if none loaded)
    region_code : Optional specific region ('region_a' or 'region_b'). If None, checks per region.

    Returns
    -------
    DataQualityReport containing results of all 12 checks.
    """
    report = DataQualityReport()

    # ---- Derive expected columns from config (Phase 2+ will have all) ----
    expected_columns = [
        "district_id", "date", "region_flag", "target",
        "slope_deg", "aspect_deg", "curvature", "twi", "elevation_m",
        "rain_3d_mm", "rain_7d_mm", "rain_15d_mm", "rain_intensity_max",
        "sm_3d_mean", "sm_event_day", "sm_tier",
        "soil_clay_pct", "soil_texture_class",
        "lulc_class", "fault_dist_km", "lithology_class",
    ]

    regions = config.get("regions", {})
    max_missing = config.get("preprocessing", {}).get("max_missing_fraction", 0.20)
    min_date_precision = config.get("acceptance_criteria", {}).get(
        "event_date_precision_min", 0.80
    )
    dem_nodata = config.get("preprocessing", {}).get("dem_nodata_value", -9999.0)

    report.add(check_01_schema(df, expected_columns))
    report.add(check_02_crs(crs_set or set(), target_crs=config.get(
        "preprocessing", {}).get("target_crs", "EPSG:4326"
    )))
    report.add(check_03_null_fraction(
        df, max_missing=max_missing,
        columns=[c for c in expected_columns if c in df.columns]
    ))
    report.add(check_04_value_ranges(df))
    report.add(check_05_duplicates(df))

    # Check 06: Spatial bounds (region-aware)
    if region_code and region_code in regions:
        bbox = regions[region_code].get("bounding_box", {})
        report.add(check_06_spatial_bounds(df, bbox))
    elif "region_flag" in df.columns and "region_a" in regions and "region_b" in regions:
        bbox_a = regions["region_a"].get("bounding_box", {})
        bbox_b = regions["region_b"].get("bounding_box", {})
        df_a = df[df["region_flag"] == 0]
        df_b = df[df["region_flag"] == 1]
        res_a = check_06_spatial_bounds(df_a, bbox_a) if not df_a.empty else None
        res_b = check_06_spatial_bounds(df_b, bbox_b) if not df_b.empty else None
        if (res_a and res_a.status == "FAIL") or (res_b and res_b.status == "FAIL"):
            fail_details = []
            if res_a and res_a.status == "FAIL":
                fail_details.append(f"Region A: {res_a.detail}")
            if res_b and res_b.status == "FAIL":
                fail_details.append(f"Region B: {res_b.detail}")
            report.add(CheckResult(
                check_id=6, name="Spatial bounds check", category="A",
                status="FAIL", detail="; ".join(fail_details),
            ))
        else:
            report.add(CheckResult(
                check_id=6, name="Spatial bounds check", category="A",
                status="PASS", detail="All district centroids within respective region bounding boxes.",
            ))
    else:
        # Fall back to envelope of all configured regions
        all_bboxes = [r.get("bounding_box", {}) for r in regions.values() if r.get("bounding_box")]
        if all_bboxes:
            combined_bbox = {
                "min_lon": min(b.get("min_lon", float("inf")) for b in all_bboxes),
                "min_lat": min(b.get("min_lat", float("inf")) for b in all_bboxes),
                "max_lon": max(b.get("max_lon", float("-inf")) for b in all_bboxes),
                "max_lat": max(b.get("max_lat", float("-inf")) for b in all_bboxes),
            }
            report.add(check_06_spatial_bounds(df, combined_bbox))
        else:
            report.add(CheckResult(
                check_id=6, name="Spatial bounds check", category="A",
                status="SKIP", detail="No region bounding boxes configured.", mandatory=False,
            ))

    report.add(check_07_catalog_crosswalk(df))
    report.add(check_08_date_precision(df, min_fraction=min_date_precision))
    report.add(check_09_class_imbalance(df))
    report.add(check_10_temporal_coverage(df))
    report.add(check_11_dem_voids(df, nodata_value=float(dem_nodata)))
    report.add(check_12_sm_tier_consistency(df))

    return report
