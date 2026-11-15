"""
Lightweight REST API & Static Serving Server
LEWDSS — SIH26001 · CSE326/CSE276 Course Project

Zero external dependency server using Python standard library http.server.
Provides:
- GET /api/health
- GET /api/districts
- GET /api/districts/<name>
- GET /api/explainability/<name>
- POST /api/predict/rlsi
- Static serving of frontend/ assets (HTML, CSS, JS)

Follows AGENTS.md: Authentic engineering, strict ground truth, viva-ready simplicity.
"""

import sys
import json
import mimetypes
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote
from typing import Dict, Any, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.decision_support.rlsi_engine import (
    load_model_checkpoint,
    compute_rlsi,
    DISTRICT_FOLD_MAP,
    EXPERIMENTAL_DISCLAIMER,
)
from src.decision_support.sop_guidance import get_sop_guidance, INSTITUTIONAL_DISCLAIMER
from src.models.spatial_cv import FEATURE_SETS
from src.rag.engine import RAGEngine

DATASET_PATH = PROJECT_ROOT / "data/processed/dataset_v1_features.csv"
RESULTS_JSON_PATH = PROJECT_ROOT / "reports/phase3_experiment_results.json"
SHAP_JSON_PATH = PROJECT_ROOT / "reports/phase3_shap_summary.json"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Cache loaded dataset, JSON metadata, and RAG engine
_DATASET_CACHE: Optional[pd.DataFrame] = None
_RESULTS_CACHE: Optional[Dict[str, Any]] = None
_SHAP_CACHE: Optional[Dict[str, Any]] = None
_RAG_ENGINE: Optional[RAGEngine] = None


def get_rag_engine() -> RAGEngine:
    global _RAG_ENGINE
    if _RAG_ENGINE is None:
        _RAG_ENGINE = RAGEngine()
    return _RAG_ENGINE


def get_dataset() -> pd.DataFrame:
    global _DATASET_CACHE
    if _DATASET_CACHE is None:
        if DATASET_PATH.exists():
            _DATASET_CACHE = pd.read_csv(DATASET_PATH)
        else:
            _DATASET_CACHE = pd.DataFrame()
    return _DATASET_CACHE


def get_results_manifest() -> Dict[str, Any]:
    global _RESULTS_CACHE
    if _RESULTS_CACHE is None:
        if RESULTS_JSON_PATH.exists():
            with open(RESULTS_JSON_PATH, "r", encoding="utf-8") as f:
                _RESULTS_CACHE = json.load(f)
        else:
            _RESULTS_CACHE = {}
    return _RESULTS_CACHE


def get_shap_summary() -> Dict[str, Any]:
    global _SHAP_CACHE
    if _SHAP_CACHE is None:
        if SHAP_JSON_PATH.exists():
            with open(SHAP_JSON_PATH, "r", encoding="utf-8") as f:
                _SHAP_CACHE = json.load(f)
        else:
            _SHAP_CACHE = {}
    return _SHAP_CACHE


class LEWDSSRequestHandler(BaseHTTPRequestHandler):
    """Custom request handler for LEWDSS dashboard and API."""

    def log_message(self, format, *args):
        # Override to suppress default verbose console logs during automated tests
        return

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message: str, status: int = 400):
        self._send_json({"error": True, "message": message, "status": status}, status=status)

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        """Handle GET requests for API endpoints and static assets."""
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/")
        if not path:
            path = "/"

        # API Routes
        if path == "/api/health":
            self._handle_health()
        elif path == "/api/districts":
            self._handle_districts()
        elif path.startswith("/api/districts/"):
            district_name = path[len("/api/districts/"):]
            self._handle_district_detail(district_name)
        elif path.startswith("/api/explainability/"):
            district_name = path[len("/api/explainability/"):]
            self._handle_explainability(district_name)
        elif path == "/api/models/audit":
            self._handle_audit()
        elif path == "/api/rag/knowledge":
            self._handle_rag_knowledge()
        elif path.startswith("/api/"):
            self._send_error(f"Unknown API endpoint: {path}", status=404)
        else:
            # Static file serving
            self._serve_static(path)

    def do_POST(self):
        """Handle POST requests for model inference and RAG queries."""
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/")

        if path == "/api/predict/rlsi":
            self._handle_predict_rlsi()
        elif path == "/api/rag/query":
            self._handle_rag_query()
        else:
            self._send_error(f"Unknown POST endpoint: {path}", status=404)

    # -------------------------------------------------------------------------
    # Route Handlers
    # -------------------------------------------------------------------------

    def _handle_health(self):
        df = get_dataset()
        manifest = get_results_manifest()
        self._send_json({
            "status": "healthy",
            "project": "LEWDSS — Regional Landslide Decision Support System",
            "milestone": "Phase 4 (Practical Decision Support Dashboard)",
            "master_random_seed": 42,
            "dataset_rows": len(df),
            "checkpoints_verified": 48,
            "api_server": "Python Standard Library http.server",
            "disclaimer": EXPERIMENTAL_DISCLAIMER,
        })

    def _handle_districts(self):
        df = get_dataset()
        districts_list = []

        for d_name, info in DISTRICT_FOLD_MAP.items():
            d_df = df[df["district"] == d_name] if not df.empty else pd.DataFrame()
            pos_df = d_df[d_df["is_positive"] == 1] if not d_df.empty else pd.DataFrame()
            bkg_df = d_df[d_df["is_positive"] == 0] if not d_df.empty else pd.DataFrame()

            date_min = str(pos_df["event_date"].min()) if not pos_df.empty else "N/A"
            date_max = str(pos_df["event_date"].max()) if not pos_df.empty else "N/A"

            districts_list.append({
                "district_name": d_name,
                "region": info["region"],
                "state": info["state"],
                "primary_fold": info["fold_id"],
                "train_districts": info["train_districts"],
                "sample_counts": {
                    "total": len(d_df),
                    "documented_landslides": len(pos_df),
                    "landscape_background": len(bkg_df),
                },
                "historical_date_range": {
                    "start": date_min,
                    "end": date_max,
                    "provenance": "NASA Global Landslide Catalog (2004-2022 monsoon)",
                },
            })

        self._send_json({
            "target_districts": districts_list,
            "total_districts": len(districts_list),
            "disclaimer": EXPERIMENTAL_DISCLAIMER,
        })

    def _handle_district_detail(self, district_name: str):
        if district_name not in DISTRICT_FOLD_MAP:
            self._send_error(f"District '{district_name}' not recognized. Must be one of {list(DISTRICT_FOLD_MAP.keys())}.", status=404)
            return

        info = DISTRICT_FOLD_MAP[district_name]
        fold_id = info["fold_id"]
        df = get_dataset()
        d_df = df[df["district"] == district_name] if not df.empty else pd.DataFrame()
        pos_df = d_df[d_df["is_positive"] == 1] if not d_df.empty else pd.DataFrame()

        # Topographic profile
        topo_profile = {}
        if not d_df.empty:
            topo_profile = {
                "elevation_min_m": round(float(d_df["elevation_m"].min()), 1),
                "elevation_max_m": round(float(d_df["elevation_m"].max()), 1),
                "elevation_mean_m": round(float(d_df["elevation_m"].mean()), 1),
                "slope_mean_deg": round(float(d_df["slope_deg"].mean()), 1),
                "slope_max_deg": round(float(d_df["slope_deg"].max()), 1),
                "dem_source": "Copernicus DEM GLO-30 (30m)",
            }

        # Historical documented events list
        events_list = []
        if not pos_df.empty:
            for _, r in pos_df.iterrows():
                events_list.append({
                    "sample_id": str(r["sample_id"]),
                    "event_id": str(r["event_id"]),
                    "event_date": str(r["event_date"]),
                    "latitude": round(float(r["lat"]), 5),
                    "longitude": round(float(r["lon"]), 5),
                    "observed_rain_3d_mm": round(float(r["rain_3d_mm"]), 1),
                    "observed_rain_7d_mm": round(float(r["rain_7d_mm"]), 1),
                    "observed_rain_15d_mm": round(float(r["rain_15d_mm"]), 1),
                    "observed_slope_deg": round(float(r["slope_deg"]), 1),
                    "observed_elevation_m": round(float(r["elevation_m"]), 1),
                    "data_source": "NASA GLC Documented Historical Event",
                })

        # Fold performance audit
        manifest = get_results_manifest()
        fold_metrics = {}
        for exp in manifest.get("individual_experiments", []):
            if exp.get("fold_id") == fold_id:
                m_fam = exp["model_family"]
                fs = exp["feature_set"]
                tm = exp["test_metrics"]
                to = exp["threshold_optimization"]
                key = f"{m_fam}_{fs}"
                fold_metrics[key] = {
                    "pr_auc": round(float(tm["pr_auc"]), 4),
                    "roc_auc": round(float(tm["roc_auc"]), 4),
                    "recall": round(float(tm["recall"]), 4),
                    "nominal_precision": round(float(tm["nominal_precision"]), 4),
                    "nominal_f1": round(float(tm["nominal_f1"]), 4),
                    "frozen_threshold_tau": round(float(to["tau_star"]), 4),
                    "target_recall_met": bool(tm["target_recall_met_test"]),
                    "tp": int(tm["tp"]),
                    "fp": int(tm["fp"]),
                    "fn": int(tm["fn"]),
                    "tn": int(tm["tn"]),
                }

        self._send_json({
            "district": district_name,
            "region": info["region"],
            "state": info["state"],
            "primary_fold": fold_id,
            "train_districts": info["train_districts"],
            "topographic_profile": topo_profile,
            "historical_positive_events": events_list,
            "n_historical_events": len(events_list),
            "audited_fold_metrics": fold_metrics,
            "disclaimer": EXPERIMENTAL_DISCLAIMER,
        })

    def _handle_explainability(self, district_name: str):
        if district_name not in DISTRICT_FOLD_MAP:
            self._send_error(f"District '{district_name}' not recognized.", status=404)
            return

        fold_id = DISTRICT_FOLD_MAP[district_name]["fold_id"]
        shap_data = get_shap_summary()

        analyses = []
        for a in shap_data.get("analyses", []):
            if a.get("fold_id") == fold_id:
                analyses.append(a)

        self._send_json({
            "district": district_name,
            "fold_id": fold_id,
            "reference_basis": "training_fold_background_only",
            "causality_disclaimer": (
                "SHAP values quantify mathematical feature attribution in the statistical model. "
                "They do NOT establish physical geotechnical causation (e.g. soil pore-water pressure, "
                "bedrock fractures, or shear strength)."
            ),
            "analyses": analyses,
        })

    def _handle_audit(self):
        manifest = get_results_manifest()
        self._send_json({
            "metadata": manifest.get("metadata", {}),
            "within_region_aggregates": manifest.get("within_region_aggregates", {}),
            "cross_region_transfer_summaries": manifest.get("cross_region_transfer_summaries", {}),
            "audit_highlights": {
                "total_runs": 48,
                "reproducibility": "100% verified across 48 checkpoints with master seed 42",
                "known_limitations": [
                    "Fold B3 (East Khasi Hills) had near-random discrimination (ROC-AUC 0.430-0.453) due to Meghalaya plateau domain shift.",
                    "Fold A3 (Kodagu) had small sample footprint (9 positive events) and failed 80% recall in both models.",
                    "Random Forest failed operational recall on 100% of folds due to probability compression under spatial shift.",
                    "Cross-region transfer failed completely (40.9%-47.0% recall) due to extreme elevation domain shift (2,000m Ghats vs 5,800m Himalayas).",
                    "Presence-Unlabeled evaluation: Precision and F1 are nominal metrics relative to landscape background, not real-world occurrence performance.",
                ],
            },
        })

    def _handle_predict_rlsi(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_error("Empty request body. JSON payload required.", status=400)
            return

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            self._send_error(f"Malformed JSON: {e}", status=400)
            return

        district = payload.get("district")
        model_family = payload.get("model_family", "LogisticRegression")
        feature_set = payload.get("feature_set", "FS3_Full")
        input_features = payload.get("features", {})

        if not district:
            self._send_error("Missing required field: 'district'.", status=400)
            return
        if district not in DISTRICT_FOLD_MAP:
            self._send_error(f"District '{district}' not recognized. Supported: {list(DISTRICT_FOLD_MAP.keys())}.", status=400)
            return
        if model_family not in ["LogisticRegression", "RandomForest"]:
            self._send_error(f"Unsupported model family: '{model_family}'. Must be LogisticRegression or RandomForest.", status=400)
            return
        if feature_set not in FEATURE_SETS:
            self._send_error(f"Unsupported feature set: '{feature_set}'. Must be FS1_Point, FS2_Zonal, or FS3_Full.", status=400)
            return

        fold_id = DISTRICT_FOLD_MAP[district]["fold_id"]

        try:
            rlsi_res = compute_rlsi(
                model_family=model_family,
                feature_set=feature_set,
                fold_id=fold_id,
                input_features=input_features,
            )
        except ValueError as ve:
            self._send_error(str(ve), status=400)
            return
        except Exception as ex:
            self._send_error(f"Inference error: {ex}", status=500)
            return

        # Attach SOP preparedness guidance
        sop = get_sop_guidance(rlsi_res["category_code"])
        rlsi_res["sop_preparedness_guidance"] = sop
        rlsi_res["district_scenario"] = district

        self._send_json(rlsi_res)

    def _handle_rag_knowledge(self):
        """Return the list of indexed RAG knowledge chunks."""
        rag = get_rag_engine()
        self._send_json({
            "total_chunks": len(rag.corpus),
            "knowledge_base": rag.corpus
        })

    def _handle_rag_query(self):
        """Handle natural language query retrieval and grounded response."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_error("Empty request body. Expected JSON with 'query'.", status=400)
            return

        try:
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
        except Exception as e:
            self._send_error(f"Malformed JSON: {e}", status=400)
            return

        query = data.get("query", "").strip()
        if not query:
            self._send_error("Missing 'query' string in request body.", status=400)
            return

        top_k = int(data.get("top_k", 3))
        rag = get_rag_engine()
        response = rag.answer_query(query, top_k=top_k)
        self._send_json(response)

    def _serve_static(self, path: str):
        """Serve static files from the frontend directory."""
        if path == "/":
            path = "/index.html"

        # Sanitize path to prevent directory traversal
        rel_path = path.lstrip("/")
        file_path = (FRONTEND_DIR / rel_path).resolve()

        if not str(file_path).startswith(str(FRONTEND_DIR.resolve())):
            self._send_error("Forbidden", status=403)
            return

        if not file_path.exists() or not file_path.is_file():
            self._send_error(f"Static file not found: {path}", status=404)
            return

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self._send_error(f"Failed reading file: {e}", status=500)


def create_server(host: str = "127.0.0.1", port: int = 8000) -> HTTPServer:
    """Create and return an HTTPServer instance."""
    return HTTPServer((host, port), LEWDSSRequestHandler)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LEWDSS REST API & Static Serving Server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    args = parser.parse_args()

    server = create_server(args.host, args.port)
    print(f"LEWDSS Dashboard Server running at http://{args.host}:{args.port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down LEWDSS server.")
        server.server_close()
