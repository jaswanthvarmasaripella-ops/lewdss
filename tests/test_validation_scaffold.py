"""
tests/test_validation_scaffold.py
==================================
Regional Landslide Risk & Emergency Response Decision System — SIH26001
Blueprint v2.0 · Milestone M0

Tests for the 12 data quality checks in src/data/validation.py.

All tests in this file use synthetic (mock) DataFrames — no downloaded
data is required. These are the Category A checks that can run immediately.

Category B checks (which require downloaded data) are tested here only
for their SKIP behaviour — they should gracefully skip, not crash.

Run with:
    python -m pytest tests/test_validation_scaffold.py -v
    python -m pytest tests/test_validation_scaffold.py -v -k "m0"
"""

import numpy as np
import pandas as pd
import pytest
import yaml
from pathlib import Path

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------
from src.data.validation import (
    CheckResult,
    DataQualityError,
    DataQualityReport,
    check_01_schema,
    check_02_crs,
    check_03_null_fraction,
    check_04_value_ranges,
    check_05_duplicates,
    check_06_spatial_bounds,
    check_07_catalog_crosswalk,
    check_08_date_precision,
    check_09_class_imbalance,
    check_10_temporal_coverage,
    check_11_dem_voids,
    check_12_sm_tier_consistency,
    run_all_checks,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent.parent / "configs" / "config.yaml"


@pytest.fixture(scope="session")
def config() -> dict:
    """Load the project config.yaml."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def minimal_df() -> pd.DataFrame:
    """
    Minimal valid DataFrame with all expected columns.
    Represents a small dataset of 6 observations: 2 events + 4 non-events.
    """
    return pd.DataFrame({
        "district_id":      ["D1", "D1", "D1", "D2", "D2", "D2"],
        "date":             pd.to_datetime(["2022-08-01", "2022-08-02",
                                            "2022-08-03", "2022-08-01",
                                            "2022-08-02", "2022-08-03"]),
        "target":           [1, 0, 0, 1, 0, 0],
        "region_flag":      [0, 0, 0, 1, 1, 1],
        "slope_deg":        [25.0, 20.0, 22.0, 35.0, 30.0, 28.0],
        "aspect_deg":       [180.0, 200.0, 190.0, 270.0, 260.0, 275.0],
        "curvature":        [-0.1, -0.05, -0.08, 0.2, 0.15, 0.18],
        "twi":              [8.5, 7.0, 7.8, 9.2, 8.8, 9.0],
        "elevation_m":      [800.0, 750.0, 770.0, 1200.0, 1100.0, 1150.0],
        "rain_3d_mm":       [120.0, 80.0, 90.0, 150.0, 100.0, 110.0],
        "rain_7d_mm":       [300.0, 200.0, 220.0, 350.0, 250.0, 280.0],
        "rain_15d_mm":      [500.0, 350.0, 380.0, 600.0, 420.0, 460.0],
        "rain_intensity_max":[80.0, 50.0, 60.0, 90.0, 65.0, 70.0],
        "sm_3d_mean":       [0.35, 0.28, 0.30, 0.40, 0.32, 0.36],
        "sm_event_day":     [0.42, 0.25, 0.27, 0.45, 0.30, 0.33],
        "sm_tier":          [1, 1, 1, 2, 2, 2],
        "soil_clay_pct":    [40.0, 35.0, 38.0, 50.0, 45.0, 48.0],
        "soil_texture_class":[2, 2, 2, 3, 3, 3],
        "lulc_class":       [1, 1, 1, 2, 2, 2],
        "fault_dist_km":    [5.0, 6.0, 5.5, 3.0, 4.0, 3.5],
        "lithology_class":  [1, 1, 1, 2, 2, 2],
        "centroid_lon":     [75.5, 75.5, 75.5, 91.5, 91.5, 91.5],
        "centroid_lat":     [12.5, 12.5, 12.5, 25.5, 25.5, 25.5],
        "catalog_source":   ["NASA_GLC", "NASA_GLC", "NASA_GLC", "NASA_GLC", "NASA_GLC", "NASA_GLC"],
        "date_precision":   ["day", "day", "day", "day", "day", "day"],
    })


@pytest.fixture
def empty_df() -> pd.DataFrame:
    """Empty DataFrame with no columns."""
    return pd.DataFrame()


# ===========================================================================
# Check 1 — Schema
# ===========================================================================

class TestCheck01Schema:

    def test_m0_all_columns_present(self, minimal_df):
        cols = list(minimal_df.columns)
        result = check_01_schema(minimal_df, cols)
        assert result.status == "PASS"
        assert result.check_id == 1

    def test_m0_missing_columns_fail(self, minimal_df):
        required = list(minimal_df.columns) + ["missing_col_a", "missing_col_b"]
        result = check_01_schema(minimal_df, required)
        assert result.status == "FAIL"
        assert "missing_col_a" in result.detail

    def test_m0_empty_df_fails_if_columns_required(self, empty_df):
        result = check_01_schema(empty_df, ["district_id", "date"])
        assert result.status == "FAIL"


# ===========================================================================
# Check 2 — CRS (Category B — should SKIP when no spatial data)
# ===========================================================================

class TestCheck02CRS:

    def test_m0_skip_when_no_data(self):
        result = check_02_crs(set())
        assert result.status == "SKIP"
        assert result.mandatory is False

    def test_m0_pass_when_correct_crs(self):
        result = check_02_crs({"EPSG:4326"}, target_crs="EPSG:4326")
        assert result.status == "PASS"

    def test_m0_fail_when_mixed_crs(self):
        result = check_02_crs({"EPSG:4326", "EPSG:32643"}, target_crs="EPSG:4326")
        assert result.status == "FAIL"


# ===========================================================================
# Check 3 — Null fraction
# ===========================================================================

class TestCheck03NullFraction:

    def test_m0_pass_no_nulls(self, minimal_df):
        result = check_03_null_fraction(minimal_df, max_missing=0.20)
        assert result.status == "PASS"

    def test_m0_fail_column_exceeds_threshold(self, minimal_df):
        df = minimal_df.copy()
        df["slope_deg"] = np.nan  # 100% missing
        result = check_03_null_fraction(df, max_missing=0.20)
        assert result.status == "FAIL"
        assert "slope_deg" in result.detail

    def test_m0_pass_below_threshold(self, minimal_df):
        df = minimal_df.copy()
        df.loc[0, "slope_deg"] = np.nan  # 1/6 = 16.7% — below 20%
        result = check_03_null_fraction(df, max_missing=0.20)
        assert result.status == "PASS"

    def test_m0_fail_at_threshold(self, minimal_df):
        df = minimal_df.copy()
        # 2/6 = 33% missing — above 20%
        df.loc[0, "slope_deg"] = np.nan
        df.loc[1, "slope_deg"] = np.nan
        result = check_03_null_fraction(df, max_missing=0.20)
        assert result.status == "FAIL"


# ===========================================================================
# Check 4 — Value ranges
# ===========================================================================

class TestCheck04ValueRanges:

    def test_m0_pass_valid_ranges(self, minimal_df):
        result = check_04_value_ranges(minimal_df)
        assert result.status == "PASS"

    def test_m0_fail_negative_slope(self, minimal_df):
        df = minimal_df.copy()
        df.loc[0, "slope_deg"] = -5.0
        result = check_04_value_ranges(df)
        assert result.status == "FAIL"
        assert "slope_deg" in result.detail

    def test_m0_fail_sm_above_1(self, minimal_df):
        df = minimal_df.copy()
        df.loc[0, "sm_obs"] = 1.5  # This col isn't in minimal_df, skip gracefully
        # Use sm_event_day to test out-of-range SM
        df2 = minimal_df.copy()
        # Add sm_obs column with invalid value
        df2["sm_obs"] = 0.3
        df2.loc[0, "sm_obs"] = 1.5
        result = check_04_value_ranges(df2)
        assert result.status == "FAIL"

    def test_m0_warn_slope_above_85(self, minimal_df):
        df = minimal_df.copy()
        df.loc[0, "slope_deg"] = 87.0  # > 85 — DEM artifact warning
        result = check_04_value_ranges(df)
        # Should be WARN (> 85) but not FAIL (still <= 90)
        assert result.status in ("WARN", "PASS")

    def test_m0_pass_missing_optional_columns(self, empty_df):
        # If no relevant columns present, check should PASS (nothing to violate)
        result = check_04_value_ranges(empty_df)
        assert result.status == "PASS"


# ===========================================================================
# Check 5 — Duplicates
# ===========================================================================

class TestCheck05Duplicates:

    def test_m0_pass_no_duplicates(self, minimal_df):
        result = check_05_duplicates(minimal_df)
        assert result.status == "PASS"

    def test_m0_fail_duplicate_key(self, minimal_df):
        df = pd.concat([minimal_df, minimal_df.iloc[:1]], ignore_index=True)
        result = check_05_duplicates(df)
        assert result.status == "FAIL"
        assert "duplicate" in result.detail.lower()

    def test_m0_skip_missing_key_columns(self, empty_df):
        result = check_05_duplicates(empty_df)
        assert result.status == "SKIP"
        assert result.mandatory is False


# ===========================================================================
# Check 6 — Spatial bounds
# ===========================================================================

class TestCheck06SpatialBounds:

    BBOX = {"min_lon": 73.5, "min_lat": 8.5, "max_lon": 93.0, "max_lat": 28.5}

    def test_m0_pass_within_bounds(self, minimal_df):
        result = check_06_spatial_bounds(minimal_df, self.BBOX)
        assert result.status == "PASS"

    def test_m0_fail_outside_bounds(self, minimal_df):
        df = minimal_df.copy()
        df.loc[0, "centroid_lon"] = 50.0  # Way outside India
        result = check_06_spatial_bounds(df, self.BBOX)
        assert result.status == "FAIL"

    def test_m0_skip_missing_centroid_columns(self, empty_df):
        result = check_06_spatial_bounds(empty_df, self.BBOX)
        assert result.status == "SKIP"


# ===========================================================================
# Check 7 — Catalog crosswalk (Category B — SKIP gracefully)
# ===========================================================================

class TestCheck07CatalogCrosswalk:

    def test_m0_pass_all_events_sourced(self, minimal_df):
        df = minimal_df.copy()
        # Ensure all event rows have a catalog source
        df.loc[df["target"] == 1, "catalog_source"] = "NASA_GLC"
        result = check_07_catalog_crosswalk(df)
        assert result.status == "PASS"

    def test_m0_fail_event_without_source(self, minimal_df):
        df = minimal_df.copy()
        df.loc[df["target"] == 1, "catalog_source"] = None
        result = check_07_catalog_crosswalk(df)
        assert result.status == "FAIL"

    def test_m0_skip_missing_catalog_column(self, empty_df):
        result = check_07_catalog_crosswalk(empty_df)
        assert result.status == "SKIP"


# ===========================================================================
# Check 8 — Date precision (Category B)
# ===========================================================================

class TestCheck08DatePrecision:

    def test_m0_pass_all_day_precision(self, minimal_df):
        df = minimal_df.copy()
        df.loc[df["target"] == 1, "date_precision"] = "day"
        result = check_08_date_precision(df, min_fraction=0.80)
        assert result.status == "PASS"

    def test_m0_fail_low_day_precision(self, minimal_df):
        df = minimal_df.copy()
        df.loc[df["target"] == 1, "date_precision"] = "year"  # 0% day precision
        result = check_08_date_precision(df, min_fraction=0.80)
        assert result.status == "FAIL"
        assert "reframed" in result.detail.lower() or "susceptibility" in result.detail.lower()

    def test_m0_skip_missing_date_precision_column(self, empty_df):
        result = check_08_date_precision(empty_df)
        assert result.status == "SKIP"


# ===========================================================================
# Check 9 — Class imbalance
# ===========================================================================

class TestCheck09ClassImbalance:

    def test_m0_pass_acceptable_ratio(self, minimal_df):
        result = check_09_class_imbalance(minimal_df)
        assert result.status == "PASS"

    def test_m0_warn_excessive_imbalance(self):
        df = pd.DataFrame({
            "target": [1] + [0] * 200,  # 1:200 ratio — extreme imbalance
        })
        result = check_09_class_imbalance(df, max_ratio=15.0)
        assert result.status == "WARN"

    def test_m0_fail_zero_positives(self):
        df = pd.DataFrame({"target": [0, 0, 0, 0]})
        result = check_09_class_imbalance(df)
        assert result.status == "FAIL"

    def test_m0_skip_missing_target_column(self, empty_df):
        result = check_09_class_imbalance(empty_df)
        assert result.status == "SKIP"


# ===========================================================================
# Check 10 — Temporal coverage (Category B)
# ===========================================================================

class TestCheck10TemporalCoverage:

    def test_m0_pass_antecedent_present(self, minimal_df):
        result = check_10_temporal_coverage(minimal_df)
        assert result.status == "PASS"

    def test_m0_fail_null_antecedent_for_event(self, minimal_df):
        df = minimal_df.copy()
        df.loc[df["target"] == 1, "rain_15d_mm"] = np.nan
        result = check_10_temporal_coverage(df)
        assert result.status == "FAIL"

    def test_m0_skip_no_antecedent_columns(self, empty_df):
        result = check_10_temporal_coverage(empty_df)
        assert result.status == "SKIP"


# ===========================================================================
# Check 11 — DEM voids
# ===========================================================================

class TestCheck11DEMVoids:

    def test_m0_pass_no_voids(self, minimal_df):
        result = check_11_dem_voids(minimal_df, nodata_value=-9999.0)
        assert result.status == "PASS"

    def test_m0_fail_nodata_sentinel(self, minimal_df):
        df = minimal_df.copy()
        df.loc[0, "elevation_m"] = -9999.0
        result = check_11_dem_voids(df, nodata_value=-9999.0)
        assert result.status == "FAIL"

    def test_m0_skip_missing_elevation_column(self, empty_df):
        result = check_11_dem_voids(empty_df)
        assert result.status == "SKIP"


# ===========================================================================
# Check 12 — SM tier consistency
# ===========================================================================

class TestCheck12SMTier:

    def test_m0_pass_valid_tiers(self, minimal_df):
        result = check_12_sm_tier_consistency(minimal_df)
        assert result.status == "PASS"

    def test_m0_fail_invalid_tier_value(self, minimal_df):
        df = minimal_df.copy()
        df.loc[0, "sm_tier"] = 5  # Invalid tier
        result = check_12_sm_tier_consistency(df)
        assert result.status == "FAIL"

    def test_m0_fail_null_tier(self, minimal_df):
        df = minimal_df.copy()
        df.loc[0, "sm_tier"] = np.nan
        result = check_12_sm_tier_consistency(df)
        assert result.status == "FAIL"

    def test_m0_skip_missing_sm_tier_column(self, empty_df):
        result = check_12_sm_tier_consistency(empty_df)
        assert result.status == "SKIP"


# ===========================================================================
# DataQualityReport — orchestrator tests
# ===========================================================================

class TestDataQualityReport:

    def test_m0_report_collects_results(self):
        report = DataQualityReport()
        report.add(CheckResult(1, "Schema", "A", "PASS", "All columns present."))
        report.add(CheckResult(2, "CRS", "B", "SKIP", "No data loaded.", mandatory=False))
        assert len(report.results) == 2

    def test_m0_report_raises_on_failure(self):
        report = DataQualityReport()
        report.add(CheckResult(1, "Schema", "A", "FAIL", "Missing columns.", mandatory=True))
        with pytest.raises(DataQualityError):
            report.raise_on_failure()

    def test_m0_report_no_raise_on_warn_skip(self):
        report = DataQualityReport()
        report.add(CheckResult(1, "Schema", "A", "WARN", "Minor issue.", mandatory=False))
        report.add(CheckResult(2, "CRS", "B", "SKIP", "No data.", mandatory=False))
        report.raise_on_failure()  # Should NOT raise

    def test_m0_all_passed_property(self):
        report = DataQualityReport()
        report.add(CheckResult(1, "A", "A", "PASS", "OK."))
        report.add(CheckResult(2, "B", "B", "SKIP", "Skipped.", mandatory=False))
        assert report.all_passed is True

    def test_m0_run_all_checks_with_minimal_df(self, minimal_df, config):
        """
        End-to-end test of run_all_checks with the minimal mock DataFrame.
        All Category B checks should SKIP; Category A checks should PASS.
        The report must not raise (since SKIP is acceptable in M0).
        """
        # Add catalog_source and date_precision so checks 7/8 can PASS
        df = minimal_df.copy()
        df.loc[df["target"] == 1, "catalog_source"] = "NASA_GLC"
        df.loc[df["target"] == 1, "date_precision"] = "day"

        report = run_all_checks(df, config, crs_set=None)
        report.print_summary()
        # In M0, failures should be zero (B checks SKIP, A checks PASS on valid data)
        failures = [r for r in report.results if r.status == "FAIL"]
        assert len(failures) == 0, f"Unexpected failures: {[(r.check_id, r.detail) for r in failures]}"


# ===========================================================================
# Config loading test
# ===========================================================================

class TestConfigLoading:

    def test_m0_config_loads(self, config):
        """config.yaml must load without error and contain required keys."""
        assert "seed" in config
        assert "regions" in config
        assert "region_a" in config["regions"]
        assert "region_b" in config["regions"]
        assert "data_sources" in config
        assert config["seed"] == 42

    def test_m0_config_has_advisory_bands(self, config):
        bands = config.get("advisory", {}).get("bands", {})
        assert set(bands.keys()) == {"low", "moderate", "high", "very_high"}

    def test_m0_config_regions_have_bbox(self, config):
        for region_key in ("region_a", "region_b"):
            bbox = config["regions"][region_key].get("bounding_box", {})
            assert "min_lon" in bbox
            assert "max_lon" in bbox
            assert "min_lat" in bbox
            assert "max_lat" in bbox


# ===========================================================================
# District boundary validation test
# ===========================================================================

class TestDistrictBoundaries:

    def test_m0_target_districts_geojson_valid(self):
        """Validate presence, schema, and geometries of acquired target districts GeoJSON."""
        from src.data.validate_boundaries import validate_target_districts
        districts = validate_target_districts()
        assert len(districts) == 6
        assert set(districts.keys()) == {
            "Wayanad", "Idukki", "Kodagu", "East Sikkim", "West Sikkim", "East Khasi Hills"
        }

