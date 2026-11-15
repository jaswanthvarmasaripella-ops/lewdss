# =============================================================================
# Makefile — Regional Landslide Risk & Emergency Response Decision System
# SIH26001 · Blueprint v2.0
#
# Windows usage: nmake -f Makefile <target>
# Linux/macOS  : make <target>
#
# For cross-platform convenience, all targets also have a Python equivalent
# documented in README.md.
# =============================================================================

PYTHON = python
PIP    = pip

# ---------------------------------------------------------------------------
# Help (default target)
# ---------------------------------------------------------------------------
.PHONY: help
help:
	@echo.
	@echo  LEWDSS — Makefile targets
	@echo  ─────────────────────────────────────────────────────────
	@echo  MILESTONE M0  (Data Reconnaissance)
	@echo    install       Install M0 Python dependencies
	@echo    check-env     Verify Python version and key imports
	@echo    reconn        Open reconnaissance notebook in Jupyter
	@echo    validate-dry  Run validation checks (no data required)
	@echo    test-m0       Run M0 unit tests
	@echo.
	@echo  LATER PHASES  (locked — require M0 approval)
	@echo    preprocess    [Phase 2] Run preprocessing pipeline
	@echo    train         [Phase 3] Train LR + RF models
	@echo    evaluate      [Phase 3] Run model evaluation
	@echo    shap          [Phase 4] Compute SHAP explanations
	@echo    api           [Phase 6] Start FastAPI server
	@echo.
	@echo  UTILITIES
	@echo    test          Run all tests with coverage report
	@echo    clean         Remove __pycache__ and .pyc files
	@echo  ─────────────────────────────────────────────────────────
	@echo.

# ---------------------------------------------------------------------------
# M0 — Install dependencies
# ---------------------------------------------------------------------------
.PHONY: install
install:
	$(PIP) install -r requirements.txt
	@echo.
	@echo  [OK] M0 dependencies installed.

# ---------------------------------------------------------------------------
# M0 — Verify environment
# ---------------------------------------------------------------------------
.PHONY: check-env
check-env:
	$(PYTHON) -c "import sys; print('Python:', sys.version)"
	$(PYTHON) -c "import numpy; print('numpy:', numpy.__version__)"
	$(PYTHON) -c "import pandas; print('pandas:', pandas.__version__)"
	$(PYTHON) -c "import requests; print('requests:', requests.__version__)"
	$(PYTHON) -c "import yaml; print('pyyaml: OK')"
	$(PYTHON) -c "import pytest; print('pytest:', pytest.__version__)"
	@echo.
	@echo  [OK] Environment check passed.

# ---------------------------------------------------------------------------
# M0 — Open reconnaissance notebook
# ---------------------------------------------------------------------------
.PHONY: reconn
reconn:
	@echo  Opening Data Reconnaissance notebook...
	@echo  IMPORTANT: Run all cells manually and review outputs.
	@echo  Do NOT proceed to Phase 1 until the notebook is complete.
	jupyter notebook notebooks/00_data_reconnaissance.ipynb

# ---------------------------------------------------------------------------
# M0 — Run validation scaffolding (dry run — no downloaded data required)
# ---------------------------------------------------------------------------
.PHONY: validate-dry
validate-dry:
	$(PYTHON) -m pytest tests/test_validation_scaffold.py -v

# ---------------------------------------------------------------------------
# M0 — Run all M0 tests
# ---------------------------------------------------------------------------
.PHONY: test-m0
test-m0:
	$(PYTHON) -m pytest tests/ -v --tb=short -k "m0 or scaffold or ingestion"

# ---------------------------------------------------------------------------
# General test target (run after M0 approval and data download)
# ---------------------------------------------------------------------------
.PHONY: test
test:
	$(PYTHON) -m pytest tests/ -v --cov=src --cov-report=term-missing --tb=short

# ---------------------------------------------------------------------------
# Phase 2+ (LOCKED — only run after M0 approval)
# ---------------------------------------------------------------------------
.PHONY: preprocess
preprocess:
	@echo  [LOCKED] Phase 2 preprocessing is not yet enabled.
	@echo  Complete M0 and obtain approval before running this target.

.PHONY: train
train:
	@echo  [LOCKED] Phase 3 model training is not yet enabled.

.PHONY: evaluate
evaluate:
	@echo  [LOCKED] Phase 3 evaluation is not yet enabled.

.PHONY: shap
shap:
	@echo  [LOCKED] Phase 4 SHAP analysis is not yet enabled.

.PHONY: api
api:
	@echo  [LOCKED] Phase 6 API server is not yet enabled.

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
.PHONY: clean
clean:
	@echo  Removing __pycache__ and .pyc files...
	for /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
	del /s /q *.pyc 2>nul
	@echo  [OK] Clean complete.
