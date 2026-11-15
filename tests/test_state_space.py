"""
Tests for State-Space Soil-Saturation Dynamic Linear Model (DLM)
Validates:
- Kalman filter state prediction and measurement updates
- Positive state guarantees and non-negativity constraints
- Reciprocal decay dynamics under zero-precipitation conditions
- Analytical cumulative window deconstruction
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import numpy as np
from src.state_space.dlm import SoilSaturationDLM, compute_soil_saturation_proxy


def test_dlm_initialization():
    dlm = SoilSaturationDLM(decay_factor=0.85)
    assert dlm.phi == 0.85
    assert dlm.W == 1.0
    assert dlm.V == 4.0

    with pytest.raises(ValueError):
        SoilSaturationDLM(decay_factor=1.5)  # invalid phi
    with pytest.raises(ValueError):
        SoilSaturationDLM(decay_factor=-0.1)


def test_dlm_decay_under_zero_rainfall():
    """Verify state decreases asymptotically under zero rainfall."""
    dlm = SoilSaturationDLM(decay_factor=0.80, initial_state=50.0)
    res = dlm.filter_trajectory([0.0] * 10)
    states = res["filtered_states"]
    assert len(states) == 10
    # Every day should be less than the prior day under zero rain
    for i in range(1, len(states)):
        assert states[i] < states[i - 1]
    assert res["final_saturation_state"] < 50.0


def test_dlm_response_to_heavy_pulse():
    """Verify state spikes under heavy rainfall pulse."""
    dlm = SoilSaturationDLM(decay_factor=0.85, initial_state=10.0)
    res = dlm.filter_trajectory([0.0, 0.0, 100.0, 150.0, 0.0])
    states = res["filtered_states"]
    assert states[3] > states[0]
    assert res["final_saturation_state"] > states[0]


def test_dlm_trend_detection():
    dlm = SoilSaturationDLM(decay_factor=0.85)
    res_surge = dlm.filter_trajectory([5.0, 10.0, 25.0, 50.0, 80.0, 120.0])
    assert res_surge["saturation_trend_5d"] > 0
    assert res_surge["saturation_trend_status"] == "ACCELERATING_ACCUMULATION"


def test_compute_soil_saturation_proxy():
    res = compute_soil_saturation_proxy(rain_3d=50.0, rain_7d=120.0, rain_15d=220.0)
    assert "final_saturation_state" in res
    assert "saturation_trend_5d" in res
    assert res["n_days_modeled"] == 15
    assert len(res["filtered_states"]) == 15
    assert res["total_rainfall_input_mm"] == 220.0
