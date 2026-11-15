"""
Phase 3 Model & Spatial Cross-Validation Unit Tests
LEWDSS — SIH26001 · CSE326/CSE276 Course Project

Tests:
1. Feature set schemas and definitions (5, 14, 17 features).
2. Outer spatial splits disjointness, completeness, and group inheritance.
3. Inner spatial splits feasibility (2-fold and 3-fold) with zero outer test leakage.
4. PU classification metrics, edge cases, and nominal label interpretations.
5. Threshold optimization logic and target recall fallback policy.
6. Spatial cluster bootstrap execution and sampling unit documentation.
7. Checkpoint existence and serialization validity across all 48 models.
8. Experiment results JSON manifest validity.
9. SHAP analysis summary and causality disclaimer integrity.

Follows AGENTS.md: Authentic engineering, strict ground truth, viva-ready testing.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import joblib

from src.models.spatial_cv import (
    FEATURE_SET_1,
    FEATURE_SET_2,
    FEATURE_SET_3,
    FEATURE_SETS,
    OUTER_FOLDS,
    get_outer_splits,
    get_inner_splits,
)
from src.models.metrics import (
    compute_classification_metrics,
    optimize_threshold,
    spatial_cluster_bootstrap,
)

DATASET_PATH = Path("data/processed/dataset_v1_features.csv")
CHECKPOINTS_DIR = Path("models/checkpoints")
RESULTS_JSON_PATH = Path("reports/phase3_experiment_results.json")
SHAP_JSON_PATH = Path("reports/phase3_shap_summary.json")


@pytest.fixture(scope="module")
def dataset_df():
    assert DATASET_PATH.exists(), f"Dataset not found at {DATASET_PATH}"
    return pd.read_csv(DATASET_PATH)


def test_feature_set_definitions():
    """Verify feature sets 1, 2, 3 have exact expected counts and no duplicates."""
    assert len(FEATURE_SET_1) == 5
    assert len(FEATURE_SET_2) == 14
    assert len(FEATURE_SET_3) == 17

    # Check subset relations
    for f in FEATURE_SET_1:
        assert f in FEATURE_SET_2
    for f in FEATURE_SET_2:
        assert f in FEATURE_SET_3

    # Check uniqueness
    assert len(set(FEATURE_SET_1)) == 5
    assert len(set(FEATURE_SET_2)) == 14
    assert len(set(FEATURE_SET_3)) == 17


def test_outer_splits_disjointness_and_counts(dataset_df):
    """Verify all 8 outer folds have strictly disjoint train/test indices and exact sample counts."""
    splits = get_outer_splits(dataset_df)
    assert len(splits) == 8

    expected_totals = {
        "Fold_A1": (240, 72),
        "Fold_A2": (108, 204),
        "Fold_A3": (276, 36),
        "Fold_B1": (204, 60),
        "Fold_B2": (196, 68),
        "Fold_B3": (128, 136),
        "Fold_TR1": (312, 264),
        "Fold_TR2": (264, 312),
    }

    for fold_id, (exp_tr, exp_te) in expected_totals.items():
        s = splits[fold_id]
        tr_idx = s["train_indices"]
        te_idx = s["test_indices"]

        assert len(tr_idx) == exp_tr, f"{fold_id} train count mismatch"
        assert len(te_idx) == exp_te, f"{fold_id} test count mismatch"

        # Disjointness
        overlap = np.intersect1d(tr_idx, te_idx)
        assert len(overlap) == 0, f"Leakage: {fold_id} has overlapping indices!"


def test_inner_splits_feasibility_and_zero_leakage(dataset_df):
    """Verify inner spatial CV feasibility and proof of zero test-district leakage."""
    splits = get_outer_splits(dataset_df)

    for fold_id, s in splits.items():
        tr_idx = s["train_indices"]
        te_idx = s["test_indices"]

        inner_folds = get_inner_splits(dataset_df, tr_idx, fold_id)

        # Within-region should have 2 inner folds; cross-region should have 3 inner folds
        if fold_id.startswith("Fold_TR"):
            assert len(inner_folds) == 3
        else:
            assert len(inner_folds) == 2

        for inf in inner_folds:
            in_tr = inf["inner_train_indices"]
            in_val = inf["inner_val_indices"]

            # Inner splits must be disjoint
            assert len(np.intersect1d(in_tr, in_val)) == 0

            # Both classes must be present
            assert inf["inner_train_pos"] > 0
            assert inf["inner_train_bkg"] > 0
            assert inf["inner_val_pos"] > 0
            assert inf["inner_val_bkg"] > 0

            # ZERO LEAKAGE with outer test indices
            assert len(np.intersect1d(in_tr, te_idx)) == 0
            assert len(np.intersect1d(in_val, te_idx)) == 0


def test_classification_metrics_computation():
    """Verify compute_classification_metrics on known synthetic binary data."""
    y_true = np.array([1, 1, 0, 0])
    y_prob = np.array([0.9, 0.4, 0.3, 0.1])
    threshold = 0.5

    metrics = compute_classification_metrics(y_true, y_prob, threshold=threshold)

    assert metrics["tp"] == 1
    assert metrics["fp"] == 0
    assert metrics["fn"] == 1
    assert metrics["tn"] == 2
    assert metrics["recall"] == 0.5
    assert metrics["nominal_precision"] == 1.0
    assert metrics["frozen_threshold"] == 0.5
    assert metrics["metric_basis"] == "sampled_background_labels"
    assert 0.0 <= metrics["pr_auc"] <= 1.0
    assert 0.0 <= metrics["roc_auc"] <= 1.0


def test_optimize_threshold_fallback():
    """Verify that optimize_threshold properly handles unachievable recall targets."""
    # Create data where highest achievable recall is 50%
    y_true = np.array([1, 1, 0, 0])
    y_prob = np.array([0.9, 0.0, 0.1, 0.2])  # Second positive has prob 0.0, so at tau >= 0.05 max recall is 1/2 = 50%

    res = optimize_threshold(y_true, y_prob, target_recall=0.80)

    assert res["target_recall_met"] is False
    assert res["achieved_train_recall"] == 0.5
    assert res["limitation_note"] is not None
    assert "could not satisfy target recall constraint" in res["limitation_note"]


def test_spatial_cluster_bootstrap(dataset_df):
    """Verify spatial cluster bootstrap executes and reports cluster sampling unit."""
    splits = get_outer_splits(dataset_df)
    s = splits["Fold_A1"]
    te_idx = s["test_indices"]
    df_te = dataset_df.loc[te_idx]
    y_true = df_te["is_positive"].values
    y_prob = np.random.RandomState(42).uniform(0, 1, size=len(y_true))

    boot = spatial_cluster_bootstrap(df_te, y_true, y_prob, threshold=0.5, n_bootstraps=50, random_state=42)

    assert boot["sampling_unit"] == "spatial_coordinate_cluster"
    assert boot["n_spatial_clusters"] >= 3
    assert "limitations" in boot
    assert boot["pr_auc_95ci"] is not None
    assert len(boot["pr_auc_95ci"]) == 2


def test_all_checkpoints_exist_and_loadable():
    """Verify that all 48 model checkpoints exist in models/checkpoints and are valid joblib files."""
    assert CHECKPOINTS_DIR.exists()
    models = ["LogisticRegression", "RandomForest"]
    feature_sets = ["FS1_Point", "FS2_Zonal", "FS3_Full"]
    folds = list(OUTER_FOLDS.keys())

    expected_count = len(models) * len(feature_sets) * len(folds)
    assert expected_count == 48

    for model_name in models:
        for fs_name in feature_sets:
            for fold_id in folds:
                ckpt_path = CHECKPOINTS_DIR / f"{model_name}_{fs_name}_{fold_id}.joblib"
                assert ckpt_path.exists(), f"Missing checkpoint: {ckpt_path}"

                payload = joblib.load(ckpt_path)
                assert "model" in payload
                assert "scaler" in payload
                assert "tau_star" in payload
                assert payload["model_family"] == model_name
                assert payload["feature_set_name"] == fs_name
                assert payload["fold_id"] == fold_id


def test_experiment_results_json_manifest():
    """Verify that reports/phase3_experiment_results.json is complete and well-structured."""
    assert RESULTS_JSON_PATH.exists()
    with open(RESULTS_JSON_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["metadata"]["total_experiments_logged"] == 48
    assert "within_region_aggregates" in manifest
    assert "cross_region_transfer_summaries" in manifest
    assert len(manifest["individual_experiments"]) == 48

    for exp in manifest["individual_experiments"]:
        assert "experiment_id" in exp
        assert "threshold_optimization" in exp
        assert "test_metrics" in exp
        assert exp["test_metrics"]["metric_basis"] == "sampled_background_labels"
        assert "spatial_cluster_bootstrap" in exp


def test_shap_summary_json():
    """Verify that reports/phase3_shap_summary.json exists with causality disclaimers."""
    assert SHAP_JSON_PATH.exists()
    with open(SHAP_JSON_PATH, "r", encoding="utf-8") as f:
        shap_data = json.load(f)

    assert "causality_disclaimer" in shap_data
    assert "analyses" in shap_data
    assert len(shap_data["analyses"]) >= 12

    for a in shap_data["analyses"]:
        assert "feature_attribution_ranking" in a
        assert len(a["feature_attribution_ranking"]) > 0
        assert "attribution_vs_causation_notice" in a
