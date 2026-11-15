"""
Decision Support & RLSI Engine Module
LEWDSS — SIH26001 · CSE326/CSE276 Course Project

Provides:
- Checkpoint loading and strict feature-schema validation.
- Relative Landslide Susceptibility Index (RLSI) computation using frozen models and scalers.
- Project-defined susceptibility tier categorization based on training-selected threshold tau*.
- Disclaimers highlighting experimental status and Presence-Unlabeled evaluation boundaries.

Follows AGENTS.md: Authentic engineering, strict ground truth, viva-ready clarity.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import joblib

from src.models.spatial_cv import FEATURE_SETS, OUTER_FOLDS

CHECKPOINTS_DIR = Path("models/checkpoints")

# Canonical mapping from target district to primary within-region holdout fold
DISTRICT_FOLD_MAP: Dict[str, Dict[str, Any]] = {
    "Wayanad": {
        "fold_id": "Fold_A1",
        "region": "Region A (Western Ghats)",
        "state": "Kerala",
        "train_districts": ["Idukki", "Kodagu"],
        "test_district": "Wayanad",
    },
    "Idukki": {
        "fold_id": "Fold_A2",
        "region": "Region A (Western Ghats)",
        "state": "Kerala",
        "train_districts": ["Wayanad", "Kodagu"],
        "test_district": "Idukki",
    },
    "Kodagu": {
        "fold_id": "Fold_A3",
        "region": "Region A (Western Ghats)",
        "state": "Karnataka",
        "train_districts": ["Wayanad", "Idukki"],
        "test_district": "Kodagu",
    },
    "East Sikkim": {
        "fold_id": "Fold_B1",
        "region": "Region B (Northeast)",
        "state": "Sikkim",
        "train_districts": ["West Sikkim", "East Khasi Hills"],
        "test_district": "East Sikkim",
    },
    "West Sikkim": {
        "fold_id": "Fold_B2",
        "region": "Region B (Northeast)",
        "state": "Sikkim",
        "train_districts": ["East Sikkim", "East Khasi Hills"],
        "test_district": "West Sikkim",
    },
    "East Khasi Hills": {
        "fold_id": "Fold_B3",
        "region": "Region B (Northeast)",
        "state": "Meghalaya",
        "train_districts": ["East Sikkim", "West Sikkim"],
        "test_district": "East Khasi Hills",
    },
}

# Project-defined display categories (heuristic ranges based on frozen training tau*)
CATEGORY_LOW = "Low Relative Susceptibility"
CATEGORY_ELEVATED = "Elevated Relative Susceptibility"
CATEGORY_HIGH = "High Relative Susceptibility"

EXPERIMENTAL_DISCLAIMER = (
    "EXPERIMENTAL RELATIVE SUSCEPTIBILITY ESTIMATE — Research prototype output only. "
    "Scores represent a Relative Landslide Susceptibility Index (RLSI) ranking terrain-rainfall "
    "combinations relative to landscape background. They are NOT calibrated real-world probabilities "
    "of slope collapse, and display categories are project-defined, not official warning levels."
)


def load_model_checkpoint(
    model_family: str,
    feature_set: str,
    fold_id: str,
    checkpoints_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Load and validate a saved model checkpoint.

    Parameters
    ----------
    model_family : str
        'LogisticRegression' or 'RandomForest'.
    feature_set : str
        'FS1_Point', 'FS2_Zonal', or 'FS3_Full'.
    fold_id : str
        Outer fold identifier (e.g. 'Fold_A1', 'Fold_TR1').
    checkpoints_dir : Path, optional
        Custom directory path for checkpoints.

    Returns
    -------
    Dict[str, Any]
        Loaded checkpoint payload containing model, scaler, tau_star, features, and metadata.

    Raises
    ------
    FileNotFoundError
        If the checkpoint joblib file does not exist.
    ValueError
        If the checkpoint metadata or feature schema fails validation.
    """
    ck_dir = checkpoints_dir or CHECKPOINTS_DIR
    filename = f"{model_family}_{feature_set}_{fold_id}.joblib"
    checkpoint_path = ck_dir / filename

    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"Checkpoint file not found: {checkpoint_path}. "
            f"Verify model_family='{model_family}', feature_set='{feature_set}', fold_id='{fold_id}'."
        )

    payload = joblib.load(checkpoint_path)

    # Validate essential keys
    required_keys = ["model", "scaler", "tau_star", "features", "model_family", "feature_set_name", "fold_id"]
    for k in required_keys:
        if k not in payload:
            raise ValueError(f"Malformed checkpoint {checkpoint_path}: missing key '{k}'.")

    # Validate metadata consistency
    if payload["model_family"] != model_family:
        raise ValueError(
            f"Checkpoint model_family mismatch: file has '{payload['model_family']}', requested '{model_family}'."
        )
    if payload["feature_set_name"] != feature_set:
        raise ValueError(
            f"Checkpoint feature_set mismatch: file has '{payload['feature_set_name']}', requested '{feature_set}'."
        )
    if payload["fold_id"] != fold_id:
        raise ValueError(
            f"Checkpoint fold_id mismatch: file has '{payload['fold_id']}', requested '{fold_id}'."
        )

    # Validate feature list against canonical definition
    expected_features = FEATURE_SETS.get(feature_set)
    if expected_features is None:
        raise ValueError(f"Unknown feature set: '{feature_set}'.")
    if list(payload["features"]) != list(expected_features):
        raise ValueError(
            f"Feature schema mismatch in {checkpoint_path}!\n"
            f"Checkpoint: {payload['features']}\n"
            f"Canonical:  {expected_features}"
        )

    return payload


def categorize_rlsi(score: float, tau_star: float) -> Tuple[str, str, str]:
    """
    Categorize continuous RLSI score into project-defined display tiers.

    Parameters
    ----------
    score : float
        Continuous model output in [0.0, 1.0].
    tau_star : float
        Frozen decision threshold from training fold.

    Returns
    -------
    Tuple[str, str, str]
        (category_name, category_code, category_description)
    """
    if score >= tau_star:
        return (
            CATEGORY_HIGH,
            "HIGH",
            f"Score ({score:.3f}) meets or exceeds the empirical decision threshold (tau* = {tau_star:.3f}). "
            f"Terrain and antecedent precipitation reflect conditions associated with historical landslide events.",
        )
    elif score >= (0.50 * tau_star):
        return (
            CATEGORY_ELEVATED,
            "ELEVATED",
            f"Score ({score:.3f}) is between 50% of threshold and threshold (0.5*tau* = {0.5*tau_star:.3f}, tau* = {tau_star:.3f}). "
            f"Conditions are elevated relative to median landscape background; heightened monitoring recommended.",
        )
    else:
        return (
            CATEGORY_LOW,
            "LOW",
            f"Score ({score:.3f}) is below 50% of threshold (0.5*tau* = {0.5*tau_star:.3f}). "
            f"Conditions are within the baseline regional landscape background envelope.",
        )


def compute_rlsi(
    model_family: str,
    feature_set: str,
    fold_id: str,
    input_features: Dict[str, float],
    checkpoints_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Compute experimental RLSI score for a given feature dictionary.

    Parameters
    ----------
    model_family : str
        'LogisticRegression' or 'RandomForest'.
    feature_set : str
        'FS1_Point', 'FS2_Zonal', or 'FS3_Full'.
    fold_id : str
        Outer fold identifier.
    input_features : Dict[str, float]
        Dictionary of feature names and numeric values.
    checkpoints_dir : Path, optional
        Custom checkpoints directory.

    Returns
    -------
    Dict[str, Any]
        Dictionary with continuous score, threshold, category, feature vector, and disclaimers.

    Raises
    ------
    ValueError
        If required features are missing or invalid.
    """
    checkpoint = load_model_checkpoint(model_family, feature_set, fold_id, checkpoints_dir)
    model = checkpoint["model"]
    scaler = checkpoint["scaler"]
    tau_star = float(checkpoint["tau_star"])
    expected_features = checkpoint["features"]

    # Verify all expected features are present in input_features
    missing = [f for f in expected_features if f not in input_features]
    if missing:
        raise ValueError(
            f"Missing required features for '{feature_set}': {missing}. "
            f"All {len(expected_features)} features must be explicitly provided in exact schema."
        )

    # Build feature array in the EXACT expected column order
    feature_values = []
    for f in expected_features:
        val = input_features[f]
        try:
            val_float = float(val)
            if np.isnan(val_float) or np.isinf(val_float):
                raise ValueError(f"Feature '{f}' has non-finite value: {val}.")
            feature_values.append(val_float)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid numeric value for feature '{f}': {val}. Error: {e}")

    X_raw = np.array([feature_values], dtype=float)

    # Apply frozen scaler
    if scaler is not None:
        X_scaled = scaler.transform(X_raw)
    else:
        X_scaled = X_raw

    # Predict continuous probability / score
    probs = model.predict_proba(X_scaled)[0]
    # Class 1 is documented event / positive relative index
    rlsi_score = float(probs[1])

    category_name, category_code, category_desc = categorize_rlsi(rlsi_score, tau_star)

    # Get fold context
    fold_info = OUTER_FOLDS.get(fold_id, {})

    return {
        "rlsi_score": round(rlsi_score, 4),
        "frozen_threshold_tau": round(tau_star, 4),
        "exceeds_threshold": bool(rlsi_score >= tau_star),
        "category": category_name,
        "category_code": category_code,
        "category_description": category_desc,
        "model_family": model_family,
        "feature_set": feature_set,
        "n_features": len(expected_features),
        "fold_id": fold_id,
        "train_districts": fold_info.get("train_districts", []),
        "test_districts": fold_info.get("test_districts", []),
        "region": fold_info.get("region", "Unknown"),
        "disclaimer": EXPERIMENTAL_DISCLAIMER,
        "feature_values_used": {f: round(v, 4) for f, v in zip(expected_features, feature_values)},
    }
