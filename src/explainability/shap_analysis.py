"""
SHAP Attribution Analysis Module
LEWDSS — SIH26001 · CSE326/CSE276 Course Project

Computes SHAP (SHapley Additive exPlanations) values for fitted models using
training-fold background data as the reference distribution.

VIVA DEFENSE MANDATE — ATTRIBUTION VS. CAUSATION:
- SHAP values quantify the mathematical contribution of each feature to the model's
  relative susceptibility output score.
- SHAP values do NOT prove physical geotechnical causation (e.g. soil cohesion, pore-water
  pressure dissipation, shear strength).
- High attribution indicates model dependence on that feature in the dataset, not that
  the feature was the sole real-world trigger of slope collapse.

Follows AGENTS.md: Authentic engineering, strict ground truth, viva-ready clarity.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import pandas as pd
import joblib
import shap

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.spatial_cv import FEATURE_SETS, get_outer_splits

DATASET_PATH = Path("data/processed/dataset_v1_features.csv")
CHECKPOINTS_DIR = Path("models/checkpoints")
SHAP_JSON_PATH = Path("reports/phase3_shap_summary.json")


def analyze_model_shap(
    df: pd.DataFrame,
    checkpoint_file: Path,
    fold_id: str,
    model_family: str,
    feature_set_name: str,
    split_info: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute SHAP values for a single fitted model checkpoint using training background reference.
    """
    checkpoint = joblib.load(checkpoint_file)
    model = checkpoint["model"]
    scaler = checkpoint["scaler"]
    features = checkpoint["features"]

    train_idx = split_info["train_indices"]
    test_idx = split_info["test_indices"]

    # Training fold background data ONLY for SHAP reference
    train_bkg_mask = (df.loc[train_idx, "is_positive"] == 0).values
    X_train_raw = df.loc[train_idx, features].values
    X_train_bkg_raw = X_train_raw[train_bkg_mask]
    X_train_bkg_sc = scaler.transform(X_train_bkg_raw)

    # Test fold samples to explain
    X_test_raw = df.loc[test_idx, features].values
    y_test = df.loc[test_idx, "is_positive"].values
    X_test_sc = scaler.transform(X_test_raw)

    if model_family == "LogisticRegression":
        # LinearExplainer with training background reference
        explainer = shap.LinearExplainer(model, X_train_bkg_sc)
        shap_values = explainer.shap_values(X_test_sc)
        base_value = float(explainer.expected_value)
    elif model_family == "RandomForest":
        # TreeExplainer with training background reference
        explainer = shap.TreeExplainer(model, data=X_train_bkg_sc)
        shap_vals_raw = explainer.shap_values(X_test_sc)
        # TreeExplainer returns (n_samples, n_features, 2) or list of 2 arrays for binary classification
        if isinstance(shap_vals_raw, list):
            shap_values = shap_vals_raw[1]  # positive class
            base_value = float(explainer.expected_value[1])
        elif len(shap_vals_raw.shape) == 3:
            shap_values = shap_vals_raw[:, :, 1]
            base_value = float(explainer.expected_value[1])
        else:
            shap_values = shap_vals_raw
            base_value = float(explainer.expected_value)
    else:
        raise ValueError(f"Unsupported model family for SHAP: {model_family}")

    # Compute mean absolute SHAP values across all test instances
    mean_abs_shap = np.mean(np.abs(shap_values), axis=0)
    feature_ranking = [
        {
            "feature": feat,
            "mean_abs_shap": round(float(val), 5),
            "rank": rank + 1,
        }
        for rank, (val, feat) in enumerate(
            sorted(zip(mean_abs_shap, features), reverse=True)
        )
    ]

    # Breakdown for positive test events vs background test points
    test_pos_mask = (y_test == 1)
    test_bkg_mask = (y_test == 0)

    pos_mean_abs = (
        np.mean(np.abs(shap_values[test_pos_mask]), axis=0)
        if np.any(test_pos_mask)
        else np.zeros_like(mean_abs_shap)
    )
    bkg_mean_abs = (
        np.mean(np.abs(shap_values[test_bkg_mask]), axis=0)
        if np.any(test_bkg_mask)
        else np.zeros_like(mean_abs_shap)
    )

    return {
        "model_family": model_family,
        "feature_set": feature_set_name,
        "fold_id": fold_id,
        "test_districts": split_info["test_districts"],
        "n_test_samples": len(test_idx),
        "n_test_positives": int(np.sum(test_pos_mask)),
        "n_test_background": int(np.sum(test_bkg_mask)),
        "reference_background_samples": len(X_train_bkg_sc),
        "base_value": round(base_value, 5),
        "feature_attribution_ranking": feature_ranking,
        "top_features": [f["feature"] for f in feature_ranking[:5]],
        "attribution_vs_causation_notice": (
            "SHAP measures statistical model attribution, not physical geotechnical causation. "
            "It quantifies how features shift the model's output relative to the training-fold background."
        ),
    }


def run_shap_analysis() -> Dict[str, Any]:
    """
    Run SHAP attribution analysis across key representative folds and feature sets.
    """
    print("=" * 80)
    print("PHASE 3: SHAP EXPLAINABILITY & ATTRIBUTION ANALYSIS")
    print("LEWDSS · SIH26001 · Regional Landslide Risk Decision Support System")
    print("=" * 80)

    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset missing at {DATASET_PATH}")

    df = pd.read_csv(DATASET_PATH)
    outer_splits = get_outer_splits(df)

    # Analyze primary representative folds: Fold A1 (Wayanad), Fold B1 (East Sikkim), Fold TR1
    target_folds = ["Fold_A1", "Fold_B1", "Fold_TR1"]
    models = ["LogisticRegression", "RandomForest"]
    feature_sets = ["FS1_Point", "FS3_Full"]

    shap_results = []

    for model_name in models:
        for fs_name in feature_sets:
            for fold_id in target_folds:
                checkpoint_path = CHECKPOINTS_DIR / f"{model_name}_{fs_name}_{fold_id}.joblib"
                if not checkpoint_path.exists():
                    print(f"  [!] Checkpoint not found: {checkpoint_path}, skipping.")
                    continue

                split_info = outer_splits[fold_id]
                res = analyze_model_shap(
                    df=df,
                    checkpoint_file=checkpoint_path,
                    fold_id=fold_id,
                    model_family=model_name,
                    feature_set_name=fs_name,
                    split_info=split_info,
                )
                shap_results.append(res)
                top_3 = ", ".join([f"{f['feature']} ({f['mean_abs_shap']:.3f})" for f in res["feature_attribution_ranking"][:3]])
                print(
                    f"  [SHAP] {model_name:<18} | {fs_name:<10} | {fold_id:<8} ({', '.join(split_info['test_districts'])}) -> Top: {top_3}"
                )

    output = {
        "title": "Phase 3 SHAP Attribution Summary",
        "reference_basis": "training_fold_background_only",
        "methodology": "LinearExplainer for LogReg, TreeExplainer for RandomForest",
        "causality_disclaimer": (
            "SHAP values quantify mathematical feature attribution in the statistical model. "
            "They do NOT establish physical geotechnical causation."
        ),
        "analyses": shap_results,
    }

    SHAP_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SHAP_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved SHAP attribution summary to: {SHAP_JSON_PATH}\n")
    return output


if __name__ == "__main__":
    run_shap_analysis()
