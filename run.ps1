param(
    [Parameter(Position=0)]
    [string]$Target = "help"
)

switch ($Target.ToLower()) {
    "check-env" {
        Write-Host "--- Checking Environment ---" -ForegroundColor Cyan
        python -c "import sys; print('Python:   ', sys.version)"
        python -c "import numpy; print('numpy:    ', numpy.__version__)"
        python -c "import pandas; print('pandas:   ', pandas.__version__)"
        python -c "import requests; print('requests: ', requests.__version__)"
        python -c "import yaml; print('pyyaml:    OK')"
        python -c "import pytest; print('pytest:   ', pytest.__version__)"
        Write-Host "`n[OK] Environment check passed." -ForegroundColor Green
    }
    "test-m0" {
        Write-Host "--- Running Milestone M0 Tests ---" -ForegroundColor Cyan
        python -m pytest tests/ -v --tb=short
    }
    "validate-dry" {
        Write-Host "--- Running Validation Scaffolding Dry Run ---" -ForegroundColor Cyan
        python -m pytest tests/test_validation_scaffold.py -v
    }
    "reconn" {
        Write-Host "--- Launching Jupyter for Reconnaissance Notebook ---" -ForegroundColor Cyan
        Write-Host "IMPORTANT: Run all cells in 00_data_reconnaissance.ipynb and review outputs." -ForegroundColor Yellow
        jupyter notebook notebooks/00_data_reconnaissance.ipynb
    }
    default {
        Write-Host "`nLEWDSS - PowerShell Task Runner (Milestone M0)" -ForegroundColor Cyan
        Write-Host "---------------------------------------------------------"
        Write-Host "  .\run.ps1 check-env     Verify Python and core package imports"
        Write-Host "  .\run.ps1 test-m0       Run all M0 unit and integration tests"
        Write-Host "  .\run.ps1 validate-dry  Run the 12 data quality check scaffold"
        Write-Host "  .\run.ps1 reconn        Open 00_data_reconnaissance.ipynb"
        Write-Host "---------------------------------------------------------`n"
    }
}
