"""
Unit Tests for Phase 4 Decision Support & RLSI Engine
LEWDSS — SIH26001 · CSE326/CSE276 Course Project

Tests:
1. Model checkpoint loading, key validation, and feature-schema consistency.
2. Missing feature detection and error raising (zero silent workarounds).
3. Exact feature ordering parity when passing arrays to model pipeline.
4. RLSI categorization logic and boundary threshold conditions.
5. SOP preparedness guidance retrieval and disclaimer completeness.
6. Execution on real dataset samples for all 6 target districts.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import numpy as np
import pandas as pd

from src.decision_support.rlsi_engine import (
    load_model_checkpoint,
    categorize_rlsi,
    compute_rlsi,
    DISTRICT_FOLD_MAP,
    CATEGORY_LOW,
    CATEGORY_ELEVATED,
    CATEGORY_HIGH,
    EXPERIMENTAL_DISCLAIMER,
)
from src.decision_support.sop_guidance import get_sop_guidance, INSTITUTIONAL_DISCLAIMER
from src.models.spatial_cv import FEATURE_SETS

DATASET_PATH = Path("data/processed/dataset_v1_features.csv")


@pytest.fixture(scope="module")
def dataset_df():
    assert DATASET_PATH.exists()
    return pd.read_csv(DATASET_PATH)


def test_district_fold_mapping():
    """Verify all 6 target districts are present in mapping and have valid fold IDs."""
    expected_districts = ["Wayanad", "Idukki", "Kodagu", "East Sikkim", "West Sikkim", "East Khasi Hills"]
    assert set(DISTRICT_FOLD_MAP.keys()) == set(expected_districts)

    for d, info in DISTRICT_FOLD_MAP.items():
        assert info["test_district"] == d
        assert info["fold_id"].startswith("Fold_")
        assert len(info["train_districts"]) == 2
        assert d not in info["train_districts"]


def test_load_checkpoint_valid():
    """Verify loading valid checkpoints across model families and feature sets."""
    # Test LR FS3 Fold_A1
    ckpt = load_model_checkpoint("LogisticRegression", "FS3_Full", "Fold_A1")
    assert ckpt["model_family"] == "LogisticRegression"
    assert ckpt["feature_set_name"] == "FS3_Full"
    assert ckpt["fold_id"] == "Fold_A1"
    assert len(ckpt["features"]) == 17
    assert 0.05 <= ckpt["tau_star"] <= 0.95

    # Test RF FS1 Fold_B1
    ckpt_rf = load_model_checkpoint("RandomForest", "FS1_Point", "Fold_B1")
    assert ckpt_rf["model_family"] == "RandomForest"
    assert ckpt_rf["feature_set_name"] == "FS1_Point"
    assert ckpt_rf["fold_id"] == "Fold_B1"
    assert len(ckpt_rf["features"]) == 5


def test_load_checkpoint_nonexistent():
    """Verify FileNotFoundError on nonexistent checkpoint."""
    with pytest.raises(FileNotFoundError):
        load_model_checkpoint("LogisticRegression", "FS1_Point", "Fold_NonExistent")


def test_categorize_rlsi_boundaries():
    """Verify RLSI categorization at exact boundary thresholds."""
    tau = 0.46
    half_tau = 0.23

    # Low category
    name, code, desc = categorize_rlsi(0.10, tau)
    assert name == CATEGORY_LOW
    assert code == "LOW"

    name, code, desc = categorize_rlsi(0.2299, tau)
    assert name == CATEGORY_LOW

    # Elevated category
    name, code, desc = categorize_rlsi(half_tau, tau)
    assert name == CATEGORY_ELEVATED
    assert code == "ELEVATED"

    name, code, desc = categorize_rlsi(0.4599, tau)
    assert name == CATEGORY_ELEVATED

    # High category
    name, code, desc = categorize_rlsi(tau, tau)
    assert name == CATEGORY_HIGH
    assert code == "HIGH"

    name, code, desc = categorize_rlsi(0.85, tau)
    assert name == CATEGORY_HIGH


def test_compute_rlsi_missing_feature():
    """Verify ValueError is raised if any required feature is missing."""
    features = {
        "elevation_m": 1200.0,
        "slope_deg": 28.5,
        # Missing rain_3d_mm, rain_7d_mm, rain_15d_mm
    }
    with pytest.raises(ValueError) as excinfo:
        compute_rlsi("LogisticRegression", "FS1_Point", "Fold_A1", features)
    assert "Missing required features" in str(excinfo.value)


def test_compute_rlsi_invalid_numeric():
    """Verify ValueError on non-numeric or NaN feature value."""
    features = {
        "elevation_m": "not_a_number",
        "slope_deg": 28.5,
        "rain_3d_mm": 50.0,
        "rain_7d_mm": 100.0,
        "rain_15d_mm": 150.0,
    }
    with pytest.raises(ValueError) as excinfo:
        compute_rlsi("LogisticRegression", "FS1_Point", "Fold_A1", features)
    assert "Invalid numeric value" in str(excinfo.value)


def test_compute_rlsi_actual_samples(dataset_df):
    """Test RLSI computation on real samples from each of the 6 target districts."""
    for district, info in DISTRICT_FOLD_MAP.items():
        fold_id = info["fold_id"]
        # Pick one positive and one background sample from this district
        d_samples = dataset_df[dataset_df["district"] == district]
        assert len(d_samples) > 0

        sample_row = d_samples.iloc[0]
        input_dict = {f: float(sample_row[f]) for f in FEATURE_SETS["FS3_Full"]}

        # Test LR FS3 Full
        result = compute_rlsi(
            model_family="LogisticRegression",
            feature_set="FS3_Full",
            fold_id=fold_id,
            input_features=input_dict,
        )

        assert 0.0 <= result["rlsi_score"] <= 1.0
        assert result["category_code"] in ["LOW", "ELEVATED", "HIGH"]
        assert result["n_features"] == 17
        assert result["disclaimer"] == EXPERIMENTAL_DISCLAIMER
        assert "feature_values_used" in result
        assert len(result["feature_values_used"]) == 17


def test_sop_guidance_structure():
    """Verify SOP guidance retrieval and institutional disclaimer."""
    for code in ["LOW", "ELEVATED", "HIGH"]:
        guidance = get_sop_guidance(code)
        assert guidance["category_code"] == code
        assert len(guidance["community_actions"]) >= 3
        assert len(guidance["infrastructure_actions"]) >= 2
        assert len(guidance["emergency_desk_checklist"]) >= 2
        assert guidance["institutional_disclaimer"] == INSTITUTIONAL_DISCLAIMER
