"""
Spatial Cross-Validation Module
LEWDSS — SIH26001 · CSE326/CSE276 Course Project

Provides:
- Fixed outer spatial cross-validation splits (Leave-One-District-Out for Region A and Region B,
  plus bidirectional Cross-Region Transfer).
- Feasible inner spatial cross-validation splits across training districts for hyperparameter tuning.
- Feature set definitions (Point FS1, Zonal FS2, Full FS3).
- Strict assertions guaranteeing zero data leakage between train and test folds.

Follows AGENTS.md: Authentic engineering, strict ground truth, viva-ready clarity.
"""

from typing import Dict, List, Tuple, Any
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Approved Feature Set Definitions
# ---------------------------------------------------------------------------
FEATURE_SET_1: List[str] = [
    "elevation_m",
    "slope_deg",
    "rain_3d_mm",
    "rain_7d_mm",
    "rain_15d_mm",
]

FEATURE_SET_2: List[str] = [
    "elevation_m",
    "slope_deg",
    "rain_3d_mm",
    "rain_7d_mm",
    "rain_15d_mm",
    "slope_max_1km",
    "slope_p90_1km",
    "elev_relief_1km",
    "slope_max_3km",
    "slope_p90_3km",
    "elev_relief_3km",
    "slope_max_5km",
    "slope_p90_5km",
    "elev_relief_5km",
]

FEATURE_SET_3: List[str] = [
    "elevation_m",
    "slope_deg",
    "rain_3d_mm",
    "rain_7d_mm",
    "rain_15d_mm",
    "slope_max_1km",
    "slope_p90_1km",
    "elev_relief_1km",
    "slope_max_3km",
    "slope_p90_3km",
    "elev_relief_3km",
    "slope_max_5km",
    "slope_p90_5km",
    "elev_relief_5km",
    "rain_3km_mean_3d",
    "rain_3km_mean_7d",
    "rain_3km_mean_15d",
]

FEATURE_SETS: Dict[str, List[str]] = {
    "FS1_Point": FEATURE_SET_1,
    "FS2_Zonal": FEATURE_SET_2,
    "FS3_Full": FEATURE_SET_3,
}

# ---------------------------------------------------------------------------
# Outer Spatial Fold Definitions
# ---------------------------------------------------------------------------
OUTER_FOLDS: Dict[str, Dict[str, Any]] = {
    # Region A (Western Ghats)
    "Fold_A1": {
        "tier": "within_region",
        "region": "Region A (Western Ghats)",
        "test_district": "Wayanad",
        "train_districts": ["Idukki", "Kodagu"],
    },
    "Fold_A2": {
        "tier": "within_region",
        "region": "Region A (Western Ghats)",
        "test_district": "Idukki",
        "train_districts": ["Wayanad", "Kodagu"],
    },
    "Fold_A3": {
        "tier": "within_region",
        "region": "Region A (Western Ghats)",
        "test_district": "Kodagu",
        "train_districts": ["Wayanad", "Idukki"],
    },
    # Region B (Northeast Himalayas)
    "Fold_B1": {
        "tier": "within_region",
        "region": "Region B (Northeast)",
        "test_district": "East Sikkim",
        "train_districts": ["West Sikkim", "East Khasi Hills"],
    },
    "Fold_B2": {
        "tier": "within_region",
        "region": "Region B (Northeast)",
        "test_district": "West Sikkim",
        "train_districts": ["East Sikkim", "East Khasi Hills"],
    },
    "Fold_B3": {
        "tier": "within_region",
        "region": "Region B (Northeast)",
        "test_district": "East Khasi Hills",
        "train_districts": ["East Sikkim", "West Sikkim"],
    },
    # Cross-Region Transfer
    "Fold_TR1": {
        "tier": "cross_region",
        "region": "Cross-Region Transfer (A -> B)",
        "test_region": "Region B (Northeast)",
        "train_region": "Region A (Western Ghats)",
        "test_districts": ["East Sikkim", "West Sikkim", "East Khasi Hills"],
        "train_districts": ["Idukki", "Kodagu", "Wayanad"],
    },
    "Fold_TR2": {
        "tier": "cross_region",
        "region": "Cross-Region Transfer (B -> A)",
        "test_region": "Region A (Western Ghats)",
        "train_region": "Region B (Northeast)",
        "test_districts": ["Idukki", "Kodagu", "Wayanad"],
        "train_districts": ["East Sikkim", "West Sikkim", "East Khasi Hills"],
    },
}


def get_outer_splits(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Generate frozen outer cross-validation splits for all approved folds.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset containing at least 'district', 'region', 'is_positive', and 'sample_id'.

    Returns
    -------
    Dict[str, Dict[str, Any]]
        Dictionary keyed by fold_id containing train_indices, test_indices,
        sample counts, and district assignments.
    """
    splits = {}

    for fold_id, fold_info in OUTER_FOLDS.items():
        if fold_info["tier"] == "within_region":
            test_mask = df["district"] == fold_info["test_district"]
            train_mask = df["district"].isin(fold_info["train_districts"])
        else:
            test_mask = df["district"].isin(fold_info["test_districts"])
            train_mask = df["district"].isin(fold_info["train_districts"])

        train_indices = df.index[train_mask].to_numpy()
        test_indices = df.index[test_mask].to_numpy()

        # Strict leakage assertion: disjoint index sets
        overlap = np.intersect1d(train_indices, test_indices)
        if len(overlap) > 0:
            raise ValueError(
                f"Data leakage in {fold_id}: {len(overlap)} samples overlap between train and test!"
            )

        splits[fold_id] = {
            "fold_id": fold_id,
            "tier": fold_info["tier"],
            "region": fold_info["region"],
            "train_districts": fold_info["train_districts"],
            "test_districts": (
                [fold_info["test_district"]]
                if fold_info["tier"] == "within_region"
                else fold_info["test_districts"]
            ),
            "train_indices": train_indices,
            "test_indices": test_indices,
            "train_sample_ids": df.loc[train_indices, "sample_id"].tolist(),
            "test_sample_ids": df.loc[test_indices, "sample_id"].tolist(),
            "train_pos": int((df.loc[train_indices, "is_positive"] == 1).sum()),
            "train_bkg": int((df.loc[train_indices, "is_positive"] == 0).sum()),
            "test_pos": int((df.loc[test_indices, "is_positive"] == 1).sum()),
            "test_bkg": int((df.loc[test_indices, "is_positive"] == 0).sum()),
        }

    return splits


def get_inner_splits(
    df: pd.DataFrame, outer_train_indices: np.ndarray, fold_id: str
) -> List[Dict[str, Any]]:
    """
    Generate inner spatial cross-validation splits strictly on outer training data.

    For within-region folds (2 training districts), produces a 2-fold Leave-One-District-Out split:
      - Inner Fold 1: Train on District 1, Validate on District 2
      - Inner Fold 2: Train on District 2, Validate on District 1

    For cross-region transfer folds (3 training districts), produces a 3-fold Leave-One-District-Out split.

    Parameters
    ----------
    df : pd.DataFrame
        Full dataset.
    outer_train_indices : np.ndarray
        Index array of outer training samples.
    fold_id : str
        Outer fold identifier (e.g. 'Fold_A1', 'Fold_TR1').

    Returns
    -------
    List[Dict[str, Any]]
        List of inner folds, each containing inner_train_idx, inner_val_idx,
        training districts, and validation district.
    """
    outer_train_df = df.loc[outer_train_indices]
    fold_info = OUTER_FOLDS[fold_id]
    train_districts = fold_info["train_districts"]

    inner_folds = []
    for i, val_district in enumerate(train_districts):
        inner_train_districts = [d for d in train_districts if d != val_district]

        inner_train_mask = outer_train_df["district"].isin(inner_train_districts)
        inner_val_mask = outer_train_df["district"] == val_district

        inner_train_idx = outer_train_df.index[inner_train_mask].to_numpy()
        inner_val_idx = outer_train_df.index[inner_val_mask].to_numpy()

        # Sanity checks
        if len(inner_train_idx) == 0 or len(inner_val_idx) == 0:
            raise ValueError(f"Empty inner split in {fold_id} fold {i}")

        inner_folds.append({
            "inner_fold_id": f"{fold_id}_inner_{i+1}",
            "inner_train_indices": inner_train_idx,
            "inner_val_indices": inner_val_idx,
            "inner_train_districts": inner_train_districts,
            "inner_val_district": val_district,
            "inner_train_pos": int((df.loc[inner_train_idx, "is_positive"] == 1).sum()),
            "inner_train_bkg": int((df.loc[inner_train_idx, "is_positive"] == 0).sum()),
            "inner_val_pos": int((df.loc[inner_val_idx, "is_positive"] == 1).sum()),
            "inner_val_bkg": int((df.loc[inner_val_idx, "is_positive"] == 0).sum()),
        })

    return inner_folds
