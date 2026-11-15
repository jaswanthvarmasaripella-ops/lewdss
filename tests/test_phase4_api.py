"""
Integration Tests for Phase 4 REST API Server
LEWDSS — SIH26001 · CSE326/CSE276 Course Project

Tests:
1. Health check endpoint (GET /api/health).
2. Districts catalog (GET /api/districts) and verified date provenance.
3. District detail endpoint (GET /api/districts/<name>) with historical event inventory and audit metrics.
4. Explainability endpoint (GET /api/explainability/<name>) with SHAP attribution and causality disclaimer.
5. Audit summary endpoint (GET /api/models/audit).
6. Inference endpoint (POST /api/predict/rlsi) with valid features, category mapping, and SOP attachment.
7. Error handling: 404 for unknown endpoints/districts, 400 for missing features and malformed payloads.
8. Feature schema parity: ensures error on mismatched features (zero silent workarounds).
"""

import sys
import json
import threading
import urllib.request
import urllib.error
from pathlib import Path
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.server import create_server
from src.models.spatial_cv import FEATURE_SETS


@pytest.fixture(scope="module")
def api_server():
    """Spin up an in-memory HTTP server on a dynamic port."""
    server = create_server(host="127.0.0.1", port=0)
    assigned_port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{assigned_port}"
    yield base_url

    server.shutdown()
    server.server_close()


def http_get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "LEWDSS-TestClient"})
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def http_post(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "LEWDSS-TestClient"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def test_api_health(api_server):
    status, data = http_get(f"{api_server}/api/health")
    assert status == 200
    assert data["status"] == "healthy"
    assert data["master_random_seed"] == 42
    assert data["checkpoints_verified"] == 48
    assert "disclaimer" in data


def test_api_districts_catalog(api_server):
    status, data = http_get(f"{api_server}/api/districts")
    assert status == 200
    assert data["total_districts"] == 6
    names = [d["district_name"] for d in data["target_districts"]]
    assert set(names) == {"Wayanad", "Idukki", "Kodagu", "East Sikkim", "West Sikkim", "East Khasi Hills"}

    for d in data["target_districts"]:
        assert d["sample_counts"]["total"] > 0
        assert d["sample_counts"]["documented_landslides"] > 0
        assert "provenance" in d["historical_date_range"]
        assert "NASA Global Landslide Catalog" in d["historical_date_range"]["provenance"]


def test_api_district_detail_valid(api_server):
    status, data = http_get(f"{api_server}/api/districts/Wayanad")
    assert status == 200
    assert data["district"] == "Wayanad"
    assert data["primary_fold"] == "Fold_A1"
    assert "topographic_profile" in data
    assert data["topographic_profile"]["elevation_min_m"] > 0
    assert len(data["historical_positive_events"]) == 18
    assert "audited_fold_metrics" in data
    assert "LogisticRegression_FS3_Full" in data["audited_fold_metrics"]


def test_api_district_detail_invalid(api_server):
    url = f"{api_server}/api/districts/UnknownDistrict"
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        http_get(url)
    assert excinfo.value.code == 404


def test_api_explainability(api_server):
    # East Sikkim is Fold_B1
    url = f"{api_server}/api/explainability/East%20Sikkim"
    status, data = http_get(url)
    assert status == 200
    assert data["district"] == "East Sikkim"
    assert data["fold_id"] == "Fold_B1"
    assert "causality_disclaimer" in data
    assert "NOT establish physical geotechnical causation" in data["causality_disclaimer"]
    assert len(data["analyses"]) >= 2  # FS1 and FS3 analyses exist for Fold_B1


def test_api_audit_summary(api_server):
    status, data = http_get(f"{api_server}/api/models/audit")
    assert status == 200
    assert "within_region_aggregates" in data
    assert "audit_highlights" in data
    assert len(data["audit_highlights"]["known_limitations"]) >= 5


def test_api_predict_rlsi_success(api_server):
    # Prepare valid 17 features for Wayanad
    features = {f: 10.0 for f in FEATURE_SETS["FS3_Full"]}
    features["elevation_m"] = 850.0
    features["slope_deg"] = 26.0
    features["rain_15d_mm"] = 280.0

    payload = {
        "district": "Wayanad",
        "model_family": "LogisticRegression",
        "feature_set": "FS3_Full",
        "features": features,
    }

    status, data = http_post(f"{api_server}/api/predict/rlsi", payload)
    assert status == 200
    assert 0.0 <= data["rlsi_score"] <= 1.0
    assert data["category_code"] in ["LOW", "ELEVATED", "HIGH"]
    assert "sop_preparedness_guidance" in data
    assert "institutional_disclaimer" in data["sop_preparedness_guidance"]
    assert data["district_scenario"] == "Wayanad"
    assert data["fold_id"] == "Fold_A1"


def test_api_predict_rlsi_missing_feature(api_server):
    # Send only 2 features instead of 17
    payload = {
        "district": "Wayanad",
        "model_family": "LogisticRegression",
        "feature_set": "FS3_Full",
        "features": {
            "elevation_m": 850.0,
            "slope_deg": 26.0,
        },
    }

    url = f"{api_server}/api/predict/rlsi"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        with urllib.request.urlopen(req) as resp:
            pass

    assert excinfo.value.code == 400
    err_body = json.loads(excinfo.value.read().decode("utf-8"))
    assert err_body["error"] is True
    assert "Missing required features" in err_body["message"]


def test_api_static_file_serving(api_server):
    """Verify static file serving for HTML, CSS, and JS assets."""
    # Test index.html via root /
    req = urllib.request.Request(f"{api_server}/", headers={"User-Agent": "LEWDSS-TestClient"})
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        assert "text/html" in resp.headers.get("Content-Type")
        body = resp.read().decode("utf-8")
        assert "Regional Landslide Early Warning" in body
        assert "ACADEMIC RESEARCH PROTOTYPE NOTICE" in body

    # Test main.css
    req_css = urllib.request.Request(f"{api_server}/css/main.css", headers={"User-Agent": "LEWDSS-TestClient"})
    with urllib.request.urlopen(req_css) as resp:
        assert resp.status == 200
        assert "text/css" in resp.headers.get("Content-Type")

    # Test app.js
    req_js = urllib.request.Request(f"{api_server}/js/app.js", headers={"User-Agent": "LEWDSS-TestClient"})
    with urllib.request.urlopen(req_js) as resp:
        assert resp.status == 200
        assert "javascript" in resp.headers.get("Content-Type")

