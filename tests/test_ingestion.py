"""
tests/test_ingestion.py
=======================
Regional Landslide Risk & Emergency Response Decision System — SIH26001
Blueprint v2.0 · Milestone M0

Tests for safe download helpers and integrity checks in src/data/ingestion.py.
- Verifies dry-run protection prevents file writing without consent
- Verifies SHA-256 calculation and verification on synthetic files
- Verifies candidate sources registry
- Verifies URL probing helper with mocked network calls
"""

import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.data.ingestion import (
    DataSource,
    describe_source,
    probe_url,
    safe_download,
    verify_sha256,
    compute_sha256,
    list_candidate_sources,
    DownloadAbortedError,
    IntegrityError,
)


def test_m0_list_candidate_sources():
    """Verify registry contains candidate data sources from Blueprint v2.0."""
    sources = list_candidate_sources()
    assert len(sources) >= 10
    keys = {s["key"] for s in sources}
    assert "NASA_GLC" in keys
    assert "COPERNICUS_GLO30" in keys
    assert "CHIRPS_V2" in keys
    assert "SMAP_L3" in keys
    assert "HWSD_V2" in keys


def test_m0_describe_source():
    """Verify description outputs expected metadata dictionary."""
    meta = describe_source(DataSource.NASA_GLC)
    assert meta["blueprint_priority"] == "primary event catalog"
    assert "expected_size_mb" in meta
    assert meta["auth_required"] is False


def test_m0_safe_download_dry_run(tmp_path):
    """Verify dry_run=True prints summary and refuses to download or create destination file."""
    dest = tmp_path / "test_file.csv"
    with pytest.raises(DownloadAbortedError) as exc_info:
        safe_download(
            url="https://example.com/fake_catalog.csv",
            dest_path=dest,
            expected_size_mb=1.0,
            dry_run=True,
        )
    assert "dry_run=True" in str(exc_info.value)
    assert not dest.exists(), "Dry run must never create files on disk"


def test_m0_compute_and_verify_sha256(tmp_path):
    """Verify SHA-256 hashing detects authentic and corrupted files."""
    test_file = tmp_path / "sample.txt"
    test_content = b"CSE326 Regional Landslide Risk Decision System"
    test_file.write_bytes(test_content)

    expected_hash = hashlib.sha256(test_content).hexdigest()
    computed_hash = compute_sha256(test_file)
    assert computed_hash == expected_hash

    # Verification passes with correct hash
    assert verify_sha256(test_file, expected_hash) is True

    # Verification raises IntegrityError on mismatch
    tampered_hash = "0" * 64
    with pytest.raises(IntegrityError):
        verify_sha256(test_file, tampered_hash)


def test_m0_probe_url_mocked():
    """Verify probe_url handles reachable and unreachable endpoints cleanly."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html", "Content-Length": "1048576"}
    mock_resp.url = "https://example.com/test"
    mock_resp.elapsed.total_seconds.return_value = 0.123

    with patch("requests.head", return_value=mock_resp):
        info = probe_url("https://example.com/test", timeout=5)
        assert info["reachable"] is True
        assert info["status_code"] == 200
        assert info["content_length_mb"] == 1.0

    with patch("requests.head", side_effect=Exception("Network error")):
        info_err = probe_url("https://unreachable.invalid", timeout=1)
        assert info_err["reachable"] is False
        assert "Network error" in info_err["error"]


def test_m0_acquired_sample_files_integrity():
    """Verify integrity and readability of Phase 1 acquired sample GeoTIFFs if present on disk."""
    from PIL import Image

    raw_dir = Path("data/raw/region_a")
    dem_path = raw_dir / "Copernicus_DSM_COG_10_N11_00_E076_00_DEM.tif"
    chirps_path = raw_dir / "chirps-v2.0.2020.08.01.tif"

    if not dem_path.exists() and not chirps_path.exists():
        pytest.skip("Test sample rasters not downloaded yet -- skipping local raster check")

    if dem_path.exists():
        # Verify SHA-256
        assert verify_sha256(
            dem_path,
            "717edb70dcd7f132ebf44466189a9f461d8137b3c36713ee407b8456f1f14884",
        )
        # Verify PIL readability and dimensions
        with Image.open(dem_path) as img:
            assert img.size == (3600, 3600)
            assert img.mode == "F"

    if chirps_path.exists():
        # Verify SHA-256
        assert verify_sha256(
            chirps_path,
            "9a71158a363e345296bfcb4795b5c5760a9bfc0eb8a3cf741924dbcd7eb00fb0",
        )
        # Verify PIL readability and dimensions
        with Image.open(chirps_path) as img:
            assert img.size == (7200, 2000)
            assert img.mode == "F"

    # Verify UGLC tiles if present
    uglc_a = Path("data/raw/region_a/UGLC_point_tile_11_4.gpkg")
    uglc_b1 = Path("data/raw/region_b/UGLC_point_tile_11_5.gpkg")
    uglc_b2 = Path("data/raw/region_b/UGLC_point_tile_12_5.gpkg")

    if uglc_a.exists():
        assert verify_sha256(
            uglc_a,
            "f22afea1626d79124fad351deb7e747fb295414ad39dbb4a920b9b355cf609ac",
        )
    if uglc_b1.exists():
        assert verify_sha256(
            uglc_b1,
            "ddfa37b9dbdd6f86eb3f0b49158b09b1214dc266376b4feeb79d976751dadb8b",
        )
    if uglc_b2.exists():
        assert verify_sha256(
            uglc_b2,
            "4016bfd1cf8c6d0581658a664ce608484823e2bb3ee45a59d785dbbdcabcff24",
        )


