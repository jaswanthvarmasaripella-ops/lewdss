"""
Evaluation Metrics & Threshold Optimization Module
LEWDSS — SIH26001 · CSE326/CSE276 Course Project

Provides:
- Presence-Unlabeled (PU) compliant evaluation metrics:
  PR-AUC, ROC-AUC, Nominal Precision, Recall, Nominal F1, Brier Score.
- Training-only threshold optimization subject to target recall constraint (>= 80%).
- Honest fallback policy: records actual achieved recall and sets target_recall_met = False
  if the target is unachieved.
- Spatial block / cluster bootstrap for uncertainty estimation respecting spatial grouping.

METHODOLOGICAL DISCLAIMER (VIVA DEFENSE MANDATE):
All metrics are evaluated against binary sampled background labels (s in {0, 1}),
where s=0 represents 5 km-buffered landscape background locations, NOT confirmed non-landslides.
Metrics evaluate relative discrimination between documented catalog events and the background landscape,
NEVER verified real-world occurrence-prediction performance.
"""

from typing import Dict, Any, Tuple, Optional, List
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.cluster import KMeans


def compute_classification_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float = 0.50,
) -> Dict[str, Any]:
    """
    Compute PU-compliant classification metrics against sampled background labels.

    Parameters
    ----------
    y_true : np.ndarray
        Binary indicators (1 = positive documented event, 0 = sampled background).
    y_prob : np.ndarray
        Predicted continuous scores / relative susceptibility probabilities.
    threshold : float
        Decision threshold tau* (applied to y_prob).

    Returns
    -------
    Dict[str, Any]
        Dictionary of classification metrics and confusion matrix components.
    """
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob).astype(float)
    y_pred = (y_prob >= threshold).astype(int)

    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))

    # PR-AUC (Average Precision)
    try:
        pr_auc = float(average_precision_score(y_true, y_prob))
    except Exception:
        pr_auc = float("nan")

    # ROC-AUC
    try:
        if len(np.unique(y_true)) > 1:
            roc_auc = float(roc_auc_score(y_true, y_prob))
        else:
            roc_auc = float("nan")
    except Exception:
        roc_auc = float("nan")

    # Nominal Precision (against sampled background)
    nominal_precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0

    # Recall (Sensitivity to true documented historical landslides)
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0

    # Nominal F1-Score
    if (nominal_precision + recall) > 0:
        nominal_f1 = float(2 * nominal_precision * recall / (nominal_precision + recall))
    else:
        nominal_f1 = 0.0

    # Brier Score (Mean Squared Probability Error)
    brier_score = float(np.mean((y_prob - y_true) ** 2))

    return {
        "pr_auc": pr_auc,
        "roc_auc": roc_auc,
        "nominal_precision": nominal_precision,
        "recall": recall,
        "nominal_f1": nominal_f1,
        "brier_score": brier_score,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "total_samples": len(y_true),
        "frozen_threshold": float(threshold),
        "metric_basis": "sampled_background_labels",
    }


def optimize_threshold(
    y_true_train: np.ndarray,
    y_prob_train: np.ndarray,
    target_recall: float = 0.80,
    thresholds: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Select operational decision threshold tau* strictly on training data.

    Optimization Objective:
        Maximize training Nominal F1 subject to Recall_train >= target_recall (default 80%).

    Fallback Policy:
        If no threshold achieves >= target_recall, select the threshold yielding the
        maximum feasible recall, record the limitation, and flag target_recall_met = False.
        Never claim target compliance when unmet.

    Parameters
    ----------
    y_true_train : np.ndarray
        Training binary indicators.
    y_prob_train : np.ndarray
        Training predicted probabilities.
    target_recall : float
        Minimum recall required (default 0.80).
    thresholds : np.ndarray, optional
        Candidate thresholds to evaluate. Defaults to 91 thresholds in [0.05, 0.95].

    Returns
    -------
    Dict[str, Any]
        Threshold optimization result dictionary.
    """
    y_true_train = np.asarray(y_true_train).astype(int)
    y_prob_train = np.asarray(y_prob_train).astype(float)

    if thresholds is None:
        thresholds = np.linspace(0.05, 0.95, 91)

    best_tau = 0.50
    best_f1 = -1.0
    achieved_recall = 0.0
    target_met = False

    # First pass: find tau satisfying recall >= target_recall with max F1
    for tau in thresholds:
        preds = (y_prob_train >= tau).astype(int)
        tp = np.sum((preds == 1) & (y_true_train == 1))
        fp = np.sum((preds == 1) & (y_true_train == 0))
        fn = np.sum((preds == 0) & (y_true_train == 1))

        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

        if rec >= target_recall:
            if f1 > best_f1:
                best_f1 = f1
                best_tau = float(tau)
                achieved_recall = float(rec)
                target_met = True

    # Fallback pass: if no threshold satisfied the constraint, select maximum feasible recall
    limitation_note = None
    if not target_met:
        recalls = []
        f1s = []
        for tau in thresholds:
            preds = (y_prob_train >= tau).astype(int)
            tp = np.sum((preds == 1) & (y_true_train == 1))
            fp = np.sum((preds == 1) & (y_true_train == 0))
            fn = np.sum((preds == 0) & (y_true_train == 1))
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            recalls.append(rec)
            f1s.append(f1)

        max_rec = max(recalls)
        best_idx = np.argmax(recalls)
        best_tau = float(thresholds[best_idx])
        achieved_recall = float(max_rec)
        best_f1 = float(f1s[best_idx])
        target_met = False
        limitation_note = (
            f"Training data could not satisfy target recall constraint of {target_recall:.1%}. "
            f"Selected threshold tau*={best_tau:.3f} yields maximum achievable training recall of {achieved_recall:.1%}."
        )

    return {
        "tau_star": round(best_tau, 4),
        "target_recall_met": target_met,
        "target_recall_threshold": float(target_recall),
        "achieved_train_recall": round(achieved_recall, 4),
        "best_train_nominal_f1": round(best_f1, 4),
        "limitation_note": limitation_note,
    }


def spatial_cluster_bootstrap(
    df_test: pd.DataFrame,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float,
    n_bootstraps: int = 500,
    random_state: int = 42,
) -> Dict[str, Any]:
    """
    Perform a spatial block / cluster bootstrap for uncertainty estimation.

    Does NOT assume individual samples are spatially independent.
    Samples are clustered by spatial coordinates (lat, lon) into geographic blocks,
    and entire spatial blocks are resampled with replacement to estimate confidence bounds.

    Parameters
    ----------
    df_test : pd.DataFrame
        Test set DataFrame containing 'lat' and 'lon'.
    y_true : np.ndarray
        True binary labels.
    y_prob : np.ndarray
        Predicted probabilities.
    threshold : float
        Frozen decision threshold.
    n_bootstraps : int
        Number of bootstrap iterations (default 500).
    random_state : int
        Random seed for reproducibility (default 42).

    Returns
    -------
    Dict[str, Any]
        Bootstrap metrics with 95% confidence intervals and sampling unit documentation.
    """
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob).astype(float)
    n_samples = len(y_true)

    # Determine number of spatial clusters: roughly 1 cluster per 10-15 samples (min 3, max 8)
    n_clusters = max(3, min(8, n_samples // 10))
    coords = df_test[["lat", "lon"]].values

    rng = np.random.RandomState(random_state)
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    cluster_labels = kmeans.fit_predict(coords)

    unique_clusters = np.unique(cluster_labels)
    cluster_indices = {c: np.where(cluster_labels == c)[0] for c in unique_clusters}

    boot_pr_aucs = []
    boot_roc_aucs = []
    boot_recalls = []

    for _ in range(n_bootstraps):
        # Resample clusters with replacement
        sampled_clusters = rng.choice(unique_clusters, size=len(unique_clusters), replace=True)
        boot_idx = np.concatenate([cluster_indices[c] for c in sampled_clusters])

        boot_y_true = y_true[boot_idx]
        boot_y_prob = y_prob[boot_idx]

        if len(np.unique(boot_y_true)) > 1:
            try:
                boot_pr_aucs.append(average_precision_score(boot_y_true, boot_y_prob))
            except Exception:
                pass
            try:
                boot_roc_aucs.append(roc_auc_score(boot_y_true, boot_y_prob))
            except Exception:
                pass

        boot_preds = (boot_y_prob >= threshold).astype(int)
        tp = np.sum((boot_preds == 1) & (boot_y_true == 1))
        fn = np.sum((boot_preds == 0) & (boot_y_true == 1))
        if (tp + fn) > 0:
            boot_recalls.append(tp / (tp + fn))

    def _ci(vals):
        if len(vals) < 20:
            return None, None
        return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))

    pr_auc_ci = _ci(boot_pr_aucs)
    roc_auc_ci = _ci(boot_roc_aucs)
    recall_ci = _ci(boot_recalls)

    return {
        "sampling_unit": "spatial_coordinate_cluster",
        "n_spatial_clusters": int(n_clusters),
        "n_bootstraps_successful": len(boot_pr_aucs),
        "pr_auc_95ci": list(pr_auc_ci) if pr_auc_ci[0] is not None else None,
        "roc_auc_95ci": list(roc_auc_ci) if roc_auc_ci[0] is not None else None,
        "recall_95ci": list(recall_ci) if recall_ci[0] is not None else None,
        "limitations": (
            "Cluster bootstrap resamples spatial coordinate blocks to respect spatial dependence. "
            "Confidence intervals are illustrative asymptotic approximations due to finite cluster counts per district."
        ),
    }
