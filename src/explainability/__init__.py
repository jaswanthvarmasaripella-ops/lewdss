"""
Explainability package for LEWDSS (SIH26001).
Provides SHAP attribution analysis respecting training-fold reference distributions.
"""

from src.explainability.shap_analysis import run_shap_analysis

__all__ = ["run_shap_analysis"]
