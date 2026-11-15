"""
Regional Landslide Early Warning & Emergency Response Decision Support System (LEWDSS)
Main Application Server Entry Point
Course: CSE276 - Artificial Intelligence Foundations

Provides lightweight REST API endpoints and static web dashboard serving:
- Web Dashboard: http://localhost:8000/
- GeoGuard RAG AI: http://localhost:8000/chatbot.html
- Health Check: http://localhost:8000/api/health
- Relative Susceptibility Prediction: POST /api/predict/rlsi
- District Context & Medians: GET /api/districts
- SHAP Feature Attributions: GET /api/explainability/<district>
- RAG Geotechnical Knowledge: GET /api/rag/knowledge
- RAG Natural Language Query: POST /api/rag/query
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.server import create_server


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LEWDSS Web Application Server & REST API")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    args = parser.parse_args()

    server = create_server(args.host, args.port)
    print("=" * 70)
    print("  REGIONAL LANDSLIDE EARLY WARNING & DECISION SUPPORT SYSTEM (LEWDSS)")
    print("  Course: CSE276 · Artificial Intelligence Foundations")
    print(f"  Live Server running at: http://{args.host}:{args.port}/")
    print(f"  GeoGuard RAG AI Assistant: http://{args.host}:{args.port}/chatbot.html")
    print("=" * 70)
    print("Press Ctrl+C to shut down.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down LEWDSS server.")
        server.server_close()


if __name__ == "__main__":
    main()
