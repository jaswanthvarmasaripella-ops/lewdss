"""
Model Training & Spatial Evaluation Pipeline
LEWDSS — SIH26001 · CSE326/CSE276 Course Project

Trains L2-regularized Logistic Regression and Random Forest models across:
- Three feature sets (FS1_Point, FS2_Zonal, FS3_Full)
- Eight spatial folds (Fold_A1, Fold_A2, Fold_A3, Fold_B1, Fold_B2, Fold_B3, Fold_TR1, Fold_TR2)

Guarantees:
- Preprocessing (StandardScaler) fitted strictly on training data.
- Hyperparameter tuning conducted via inner spatial cross-validation on training data only.
- Threshold selection tau* optimized on training data only (max F1 @ Recall >= 80%).
- Target recall deficit policy: reports actual achieved recall without false claims.
- Checkpoint serialization to models/checkpoints/.
- Complete results saved to reports/phase3_experiment_results.json.

Follows AGENTS.md: Authentic engineering, strict ground truth, viva-ready clarity.
"""

import os
import sys
import json
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import joblib

from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

from src.models.spatial_cv import (
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

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RANDOM_SEED = 42
DATASET_PATH = Path("data/processed/dataset_v1_features.csv")
CHECKPOINTS_DIR = Path("models/checkpoints")
RESULTS_JSON_PATH = Path("reports/phase3_experiment_results.json")

# Hyperparameter search grids (evaluated strictly via inner spatial CV)
LR_PARAM_GRID = [0.01, 0.1, 1.0, 10.0]  # Regularization parameter C

RF_PARAM_GRID = [
    {"max_depth": 4, "min_samples_leaf": 3},
    {"max_depth": 4, "min_samples_leaf": 5},
    {"max_depth": 6, "min_samples_leaf": 3},
    {"max_depth": 6, "min_samples_leaf": 5},
]


def tune_logistic_regression(
    df: pd.DataFrame,
    train_indices: np.ndarray,
    features: List[str],
    fold_id: str,
) -> float:
    """
    Select optimal C parameter for Logistic Regression via inner spatial CV on training data.
    """
    inner_splits = get_inner_splits(df, train_indices, fold_id)
    best_c = 1.0
    best_loss = float("inf")

    for c in LR_PARAM_GRID:
        fold_losses = []
        for inner_fold in inner_splits:
            in_tr_idx = inner_fold["inner_train_indices"]
            in_val_idx = inner_fold["inner_val_indices"]

            X_in_tr = df.loc[in_tr_idx, features].values
            y_in_tr = df.loc[in_tr_idx, "is_positive"].values
            X_in_val = df.loc[in_val_idx, features].values
            y_in_val = df.loc[in_val_idx, "is_positive"].values

            scaler = StandardScaler()
            X_in_tr_sc = scaler.fit_transform(X_in_tr)
            X_in_val_sc = scaler.transform(X_in_val)

            model = LogisticRegression(
                C=c,
                solver="lbfgs",
                class_weight="balanced",
                random_state=RANDOM_SEED,
                max_iter=1000,
            )
            model.fit(X_in_tr_sc, y_in_tr)

            probs = model.predict_proba(X_in_val_sc)[:, 1]
            probs = np.clip(probs, 1e-15, 1 - 1e-15)
            loss = -np.mean(y_in_val * np.log(probs) + (1 - y_in_val) * np.log(1 - probs))
            fold_losses.append(loss)

        avg_loss = float(np.mean(fold_losses))
        if avg_loss < best_loss:
            best_loss = avg_loss
            best_c = c

    return best_c


def tune_random_forest(
    df: pd.DataFrame,
    train_indices: np.ndarray,
    features: List[str],
    fold_id: str,
) -> Dict[str, Any]:
    """
    Select optimal tree depth and leaf samples for Random Forest via inner spatial CV.
    """
    inner_splits = get_inner_splits(df, train_indices, fold_id)
    best_params = RF_PARAM_GRID[0]
    best_loss = float("inf")

    for params in RF_PARAM_GRID:
        fold_losses = []
        for inner_fold in inner_splits:
            in_tr_idx = inner_fold["inner_train_indices"]
            in_val_idx = inner_fold["inner_val_indices"]

            X_in_tr = df.loc[in_tr_idx, features].values
            y_in_tr = df.loc[in_tr_idx, "is_positive"].values
            X_in_val = df.loc[in_val_idx, features].values
            y_in_val = df.loc[in_val_idx, "is_positive"].values

            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=params["max_depth"],
                min_samples_leaf=params["min_samples_leaf"],
                class_weight="balanced_subsample",
                random_state=RANDOM_SEED,
                n_jobs=-1,
            )
            model.fit(X_in_tr, y_in_tr)

            probs = model.predict_proba(X_in_val)[:, 1]
            probs = np.clip(probs, 1e-15, 1 - 1e-15)
            loss = -np.mean(y_in_val * np.log(probs) + (1 - y_in_val) * np.log(1 - probs))
            fold_losses.append(loss)

        avg_loss = float(np.mean(fold_losses))
        if avg_loss < best_loss:
            best_loss = avg_loss
            best_params = params

    return best_params


def train_and_evaluate_single_experiment(
    df: pd.DataFrame,
    model_family: str,
    feature_set_name: str,
    fold_id: str,
    split_info: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute a single model-feature-fold experiment with zero test-fold leakage.
    """
    features = FEATURE_SETS[feature_set_name]
    train_idx = split_info["train_indices"]
    test_idx = split_info["test_indices"]

    X_train_raw = df.loc[train_idx, features].values
    y_train = df.loc[train_idx, "is_positive"].values.astype(int)
    X_test_raw = df.loc[test_idx, features].values
    y_test = df.loc[test_idx, "is_positive"].values.astype(int)
    df_test = df.loc[test_idx]

    # Preprocessing: StandardScaler fitted strictly on training fold
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train_raw)
    X_test_sc = scaler.transform(X_test_raw)

    # Hyperparameter tuning strictly on inner training folds
    if model_family == "LogisticRegression":
        best_c = tune_logistic_regression(df, train_idx, features, fold_id)
        selected_params = {"C": best_c, "solver": "lbfgs", "class_weight": "balanced"}
        model = LogisticRegression(
            C=best_c,
            solver="lbfgs",
            class_weight="balanced",
            random_state=RANDOM_SEED,
            max_iter=1000,
        )
        model.fit(X_train_sc, y_train)
        train_probs = model.predict_proba(X_train_sc)[:, 1]
        test_probs = model.predict_proba(X_test_sc)[:, 1]

    elif model_family == "RandomForest":
        best_rf_params = tune_random_forest(df, train_idx, features, fold_id)
        selected_params = {
            "n_estimators": 100,
            "max_depth": best_rf_params["max_depth"],
            "min_samples_leaf": best_rf_params["min_samples_leaf"],
            "class_weight": "balanced_subsample",
        }
        # Random Forest uses unscaled or scaled features; using scaled keeps feature distributions standard
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=best_rf_params["max_depth"],
            min_samples_leaf=best_rf_params["min_samples_leaf"],
            class_weight="balanced_subsample",
            random_state=RANDOM_SEED,
            n_jobs=-1,
        )
        model.fit(X_train_sc, y_train)
        train_probs = model.predict_proba(X_train_sc)[:, 1]
        test_probs = model.predict_proba(X_test_sc)[:, 1]
    else:
        raise ValueError(f"Unknown model family: {model_family}")

    # Decision Threshold Optimization strictly on training fold
    thresh_opt = optimize_threshold(y_train, train_probs, target_recall=0.80)
    tau_star = thresh_opt["tau_star"]

    # Evaluation on held-out test fold using frozen tau*
    test_metrics = compute_classification_metrics(y_test, test_probs, threshold=tau_star)
    test_target_recall_met = bool(test_metrics["recall"] >= 0.80)

    # Spatial cluster bootstrap for uncertainty
    bootstrap_results = spatial_cluster_bootstrap(
        df_test=df_test,
        y_true=y_test,
        y_prob=test_probs,
        threshold=tau_star,
        n_bootstraps=500,
        random_state=RANDOM_SEED,
    )

    # Save model checkpoint
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_file = CHECKPOINTS_DIR / f"{model_family}_{feature_set_name}_{fold_id}.joblib"
    checkpoint_payload = {
        "model": model,
        "scaler": scaler,
        "tau_star": tau_star,
        "features": features,
        "model_family": model_family,
        "feature_set_name": feature_set_name,
        "fold_id": fold_id,
        "selected_params": selected_params,
        "random_seed": RANDOM_SEED,
    }
    joblib.dump(checkpoint_payload, checkpoint_file)

    experiment_record = {
        "experiment_id": f"EXP_{model_family}_{feature_set_name}_{fold_id}",
        "model_family": model_family,
        "feature_set": feature_set_name,
        "n_features": len(features),
        "features": features,
        "fold_id": fold_id,
        "tier": split_info["tier"],
        "region": split_info["region"],
        "train_districts": split_info["train_districts"],
        "test_districts": split_info["test_districts"],
        "sample_counts": {
            "train_total": len(train_idx),
            "train_pos": split_info["train_pos"],
            "train_bkg": split_info["train_bkg"],
            "test_total": len(test_idx),
            "test_pos": split_info["test_pos"],
            "test_bkg": split_info["test_bkg"],
        },
        "selected_hyperparameters": selected_params,
        "threshold_optimization": {
            "tau_star": tau_star,
            "target_recall_threshold": 0.80,
            "achieved_train_recall": thresh_opt["achieved_train_recall"],
            "target_recall_met_train": thresh_opt["target_recall_met"],
            "best_train_nominal_f1": thresh_opt["best_train_nominal_f1"],
            "limitation_note": thresh_opt["limitation_note"],
        },
        "test_metrics": {
            "pr_auc": test_metrics["pr_auc"],
            "roc_auc": test_metrics["roc_auc"],
            "nominal_precision": test_metrics["nominal_precision"],
            "recall": test_metrics["recall"],
            "nominal_f1": test_metrics["nominal_f1"],
            "brier_score": test_metrics["brier_score"],
            "tp": test_metrics["tp"],
            "fp": test_metrics["fp"],
            "fn": test_metrics["fn"],
            "tn": test_metrics["tn"],
            "target_recall_met_test": test_target_recall_met,
            "metric_basis": "sampled_background_labels",
        },
        "spatial_cluster_bootstrap": bootstrap_results,
        "checkpoint_path": str(checkpoint_file).replace("\\", "/"),
    }

    return experiment_record


def run_all_experiments() -> Dict[str, Any]:
    """
    Execute all 48 model-feature-fold experiments, aggregate results, and save manifest.
    """
    print("=" * 80)
    print("PHASE 3: BASELINE MODEL TRAINING & SPATIAL CROSS-VALIDATION")
    print("LEWDSS · SIH26001 · Regional Landslide Risk Decision Support System")
    print("=" * 80)

    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset missing at {DATASET_PATH}")

    df = pd.read_csv(DATASET_PATH)
    print(f"Loaded dataset: {len(df)} samples ({int((df['is_positive']==1).sum())} pos, {int((df['is_positive']==0).sum())} bkg).\n")

    outer_splits = get_outer_splits(df)
    models = ["LogisticRegression", "RandomForest"]
    feature_sets = ["FS1_Point", "FS2_Zonal", "FS3_Full"]

    all_experiments = []
    start_time = time.time()

    total_runs = len(models) * len(feature_sets) * len(outer_splits)
    current_run = 0

    print(f"Executing {total_runs} experimental runs (2 Models x 3 Feature Sets x 8 Folds)...\n")

    for model_name in models:
        for fs_name in feature_sets:
            print(f">>> Running: {model_name} | {fs_name} across 8 spatial folds...")
            for fold_id, split_info in outer_splits.items():
                current_run += 1
                rec = train_and_evaluate_single_experiment(
                    df=df,
                    model_family=model_name,
                    feature_set_name=fs_name,
                    fold_id=fold_id,
                    split_info=split_info,
                )
                all_experiments.append(rec)

                test_res = rec["test_metrics"]
                tau_info = rec["threshold_optimization"]
                test_dist = split_info["test_districts"]

                print(
                    f"  [{current_run:02d}/{total_runs}] {fold_id:<8} ({', '.join(test_dist):<16}) "
                    f"tau*={tau_info['tau_star']:.3f} | "
                    f"PR-AUC={test_res['pr_auc']:.3f} | "
                    f"ROC-AUC={test_res['roc_auc']:.3f} | "
                    f"Rec={test_res['recall']:.1%} (TargetMet={test_res['target_recall_met_test']}) | "
                    f"NomPrec={test_res['nominal_precision']:.3f} | "
                    f"NomF1={test_res['nominal_f1']:.3f}"
                )
            print()

    elapsed = time.time() - start_time
    print(f"All {total_runs} experiments completed in {elapsed:.1f}s.\n")

    # Aggregate summaries by Model x Feature Set across within-region folds (A1-A3, B1-B3)
    within_region_folds = ["Fold_A1", "Fold_A2", "Fold_A3", "Fold_B1", "Fold_B2", "Fold_B3"]
    aggregates = {}

    for model_name in models:
        aggregates[model_name] = {}
        for fs_name in feature_sets:
            subset = [
                e for e in all_experiments
                if e["model_family"] == model_name
                and e["feature_set"] == fs_name
                and e["fold_id"] in within_region_folds
            ]
            pr_aucs = [e["test_metrics"]["pr_auc"] for e in subset]
            roc_aucs = [e["test_metrics"]["roc_auc"] for e in subset]
            recalls = [e["test_metrics"]["recall"] for e in subset]
            precs = [e["test_metrics"]["nominal_precision"] for e in subset]
            f1s = [e["test_metrics"]["nominal_f1"] for e in subset]
            briers = [e["test_metrics"]["brier_score"] for e in subset]

            aggregates[model_name][fs_name] = {
                "n_within_region_folds": len(subset),
                "pr_auc_mean": round(float(np.mean(pr_aucs)), 4),
                "pr_auc_std": round(float(np.std(pr_aucs)), 4),
                "roc_auc_mean": round(float(np.mean(roc_aucs)), 4),
                "roc_auc_std": round(float(np.std(roc_aucs)), 4),
                "recall_mean": round(float(np.mean(recalls)), 4),
                "recall_std": round(float(np.std(recalls)), 4),
                "nominal_precision_mean": round(float(np.mean(precs)), 4),
                "nominal_precision_std": round(float(np.std(precs)), 4),
                "nominal_f1_mean": round(float(np.mean(f1s)), 4),
                "nominal_f1_std": round(float(np.std(f1s)), 4),
                "brier_score_mean": round(float(np.mean(briers)), 4),
                "brier_score_std": round(float(np.std(briers)), 4),
            }

    # Cross-region transfer summaries (TR1, TR2)
    transfer_summaries = {}
    for model_name in models:
        transfer_summaries[model_name] = {}
        for fs_name in feature_sets:
            tr_subset = [
                e for e in all_experiments
                if e["model_family"] == model_name
                and e["feature_set"] == fs_name
                and e["fold_id"].startswith("Fold_TR")
            ]
            transfer_summaries[model_name][fs_name] = {
                e["fold_id"]: {
                    "test_region": e["region"],
                    "pr_auc": e["test_metrics"]["pr_auc"],
                    "roc_auc": e["test_metrics"]["roc_auc"],
                    "recall": e["test_metrics"]["recall"],
                    "nominal_precision": e["test_metrics"]["nominal_precision"],
                    "nominal_f1": e["test_metrics"]["nominal_f1"],
                    "target_recall_met": e["test_metrics"]["target_recall_met_test"],
                }
                for e in tr_subset
            }

    manifest = {
        "metadata": {
            "title": "Phase 3 Model Experiment Results Manifest",
            "project": "LEWDSS — SIH26001",
            "execution_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_seconds": round(elapsed, 2),
            "master_random_seed": RANDOM_SEED,
            "dataset_rows": len(df),
            "positives": int((df["is_positive"] == 1).sum()),
            "background": int((df["is_positive"] == 0).sum()),
            "total_experiments_logged": len(all_experiments),
            "metric_disclaimer": (
                "All metrics are evaluated against binary sampled background labels (s in {0, 1}). "
                "Background points are unlabeled landscape locations, NOT confirmed negatives. "
                "Scores represent a Relative Landslide Susceptibility Index (RLSI), NOT calibrated real-world probabilities."
            ),
        },
        "within_region_aggregates": aggregates,
        "cross_region_transfer_summaries": transfer_summaries,
        "individual_experiments": all_experiments,
    }

    # Save to reports/phase3_experiment_results.json
    RESULTS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Saved complete experiment results to: {RESULTS_JSON_PATH}")
    print(f"Saved {total_runs} model checkpoints to: {CHECKPOINTS_DIR}\n")

    return manifest


if __name__ == "__main__":
    manifest = run_all_experiments()
