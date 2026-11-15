"""
src/data/ingestion.py
=====================
Regional Landslide Risk & Emergency Response Decision System -- SIH26001
Blueprint v2.0 * Milestone M0

Safe download helpers with:
  - SHA-256 file integrity verification
  - Dry-run mode (describe what would be downloaded without doing it)
  - Resume detection (skip already-downloaded files)
  - Explicit documentation of source, expected size, and access requirements
  - No automatic large-dataset downloads

USAGE POLICY
------------
This module does NOT initiate any download unless the caller explicitly passes
  dry_run=False
and has confirmed the data source, license, expected size, and destination.

All functions print a clear summary before any network request. They will
raise DownloadAbortedError if called without confirmation.

HOW TO USE IN RECONNAISSANCE NOTEBOOK
--------------------------------------
Step 1 -- Inspect a source (safe, no download):
    from src.data.ingestion import describe_source, DataSource
    describe_source(DataSource.NASA_GLC)

Step 2 -- Probe whether a URL is reachable (no data transfer, HEAD only):
    from src.data.ingestion import probe_url
    probe_url("https://data.chc.ucsb.edu/products/CHIRPS-2.0/", timeout=10)

Step 3 -- Download a small index/metadata file after confirmation:
    from src.data.ingestion import safe_download
    safe_download(
        url="https://...",
        dest_path="data/raw/region_a/glc_catalog.csv",
        expected_sha256=None,          # fill in after first download
        expected_size_mb=1.2,
        dry_run=False,                 # set False only after review
    )

Step 4 -- Verify integrity of an already-downloaded file:
    from src.data.ingestion import verify_sha256
    verify_sha256("data/raw/region_a/glc_catalog.csv", expected="abc123...")
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from enum import Enum
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DownloadAbortedError(RuntimeError):
    """Raised when a download is attempted in dry-run mode or without confirmation."""


class IntegrityError(RuntimeError):
    """Raised when SHA-256 of a downloaded file does not match expected value."""


# ---------------------------------------------------------------------------
# Known data sources -- metadata registry
# ---------------------------------------------------------------------------

class DataSource(Enum):
    """Enumeration of candidate data sources defined in Blueprint v2.0 Section 5."""
    COPERNICUS_GLO30     = "Copernicus DEM GLO-30"
    COPERNICUS_DEM       = "Copernicus DEM GLO-30"
    SRTM_30M             = "SRTM 30m (NASA EarthData)"
    CHIRPS_V2            = "CHIRPS v2.0 Daily Rainfall"
    CHIRPS_PRECIP        = "CHIRPS v2.0 Daily Rainfall"
    GPM_IMERG            = "NASA GPM IMERG Final"
    NASA_GLC             = "NASA Global Landslide Catalog"
    ISRO_BHUVAN_ATLAS    = "ISRO Bhuvan Landslide Atlas"
    SMAP_L3              = "NASA SMAP L3 Soil Moisture"
    NASA_SMAP_L3         = "NASA SMAP L3 Soil Moisture"
    GLEAM_V3             = "GLEAM v3 Soil Moisture"
    GLDAS_NOAH           = "GLDAS-2.1 Noah Soil Moisture"
    HWSD_V2              = "HWSD v2 (FAO Soil Data)"
    HWSD_SOIL            = "HWSD v2 (FAO Soil Data)"
    BHUVAN_LULC          = "ISRO Bhuvan LULC 50K"
    GSI_GEOLOGY          = "GSI Bhukosh Geological Map"
    NOAA_GFS             = "NOAA GFS Rainfall Forecast"
    DISTRICT_BOUNDARIES  = "India District Boundaries"


# Source metadata: url, access type, expected size, license, M0 notes
_SOURCE_REGISTRY: dict[DataSource, dict] = {
    DataSource.NASA_GLC: {
        "url": "https://maps.nccs.nasa.gov/arcgis/apps/MapAndAppGallery/index.html?appid=574f26408683485799d02e857e5d9521",
        "direct_download_url": "https://gpm.nasa.gov/landslides/data.html",
        "access": "open -- NASA public domain",
        "auth_required": False,
        "expected_size_mb": 2.0,
        "format": "CSV",
        "license": "NASA public domain (no restrictions)",
        "m0_action": "Probe landing page; attempt CSV download in reconnaissance",
        "india_coverage": "UNKNOWN -- verify event count and date precision in reconnaissance",
        "blueprint_priority": "primary event catalog",
    },
    DataSource.CHIRPS_V2: {
        "url": "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/tifs/p05/",
        "access": "open FTP/HTTPS -- no login required",
        "auth_required": False,
        "expected_size_per_file_mb": 5.0,
        "expected_total_size_gb": "~50 GB for 10 years daily global (do NOT bulk download)",
        "format": "GeoTIFF (.tif.gz)",
        "license": "open -- no redistribution restrictions",
        "m0_action": "Probe directory listing; download one test tile only during reconnaissance",
        "blueprint_priority": "primary rainfall source",
    },
    DataSource.COPERNICUS_GLO30: {
        "url": "https://opentopography.s3.sdsc.edu/raster/COP90/COP90_hh/",
        "access": "open -- OpenTopography S3 mirror",
        "auth_required": False,
        "expected_size_per_tile_mb": 120.0,
        "format": "GeoTIFF",
        "license": "CC-BY-4.0",
        "m0_action": "Probe S3 listing; download one 1 degx1 deg tile for connectivity test",
        "blueprint_priority": "primary DEM source",
    },
    DataSource.SRTM_30M: {
        "url": "https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/",
        "access": "NASA EarthData login required",
        "auth_required": True,
        "auth_type": "NASA EarthData (earthdata.nasa.gov -- free registration)",
        "expected_size_per_tile_mb": 25.0,
        "format": "HGT (SRTM format)",
        "license": "public domain",
        "m0_action": "Verify EarthData account; attempt one tile download in reconnaissance",
        "blueprint_priority": "DEM fallback",
    },
    DataSource.SMAP_L3: {
        "url": "https://n5eil01u.ecs.nsidc.org/SMAP/SPL3SMP.008/",
        "access": "NASA EarthData login required",
        "auth_required": True,
        "auth_type": "NASA EarthData (earthdata.nasa.gov -- free registration)",
        "expected_size_per_file_mb": 40.0,
        "temporal_coverage": "2015-04-01 to present",
        "format": "HDF5 (.h5)",
        "license": "public domain (NASA)",
        "m0_action": "Verify EarthData access; check RFI/frozen-soil mask coverage for India",
        "blueprint_priority": "Tier 1 soil moisture",
        "sm_tier": 1,
    },
    DataSource.GLEAM_V3: {
        "url": "https://www.gleam.eu/",
        "access": "free registration required at gleam.eu",
        "auth_required": True,
        "auth_type": "GLEAM portal registration (free)",
        "expected_size_total_gb": "~2 GB for surface SM",
        "temporal_coverage": "1980-01-01 to present",
        "format": "NetCDF",
        "license": "free for academic use",
        "m0_action": "Register at gleam.eu; verify download access; check India coverage",
        "blueprint_priority": "Tier 2 soil moisture",
        "sm_tier": 2,
    },
    DataSource.GLDAS_NOAH: {
        "url": "https://disc.gsfc.nasa.gov/datasets/GLDAS_NOAH025_3H_2.1/summary",
        "access": "NASA GES DISC login required",
        "auth_required": True,
        "auth_type": "NASA EarthData + GES DISC approval",
        "expected_size_per_file_mb": 15.0,
        "temporal_coverage": "2000-01-01 to present",
        "format": "NetCDF-4",
        "license": "public domain (NASA)",
        "m0_action": "Verify GES DISC access; note 3-hourly files require aggregation",
        "blueprint_priority": "Tier 2 soil moisture (alternative)",
        "sm_tier": 2,
    },
    DataSource.HWSD_V2: {
        "url": "https://www.fao.org/soils-portal/data-hub/soil-maps-and-databases/harmonized-world-soil-database-v20/en/",
        "access": "open -- no login required",
        "auth_required": False,
        "expected_size_mb": 300.0,
        "format": "GeoTIFF + MDB (Access database)",
        "license": "open for academic use",
        "m0_action": "Probe FAO portal; confirm current download link still active",
        "blueprint_priority": "soil texture + Tier 3 SM proxy",
    },
    DataSource.ISRO_BHUVAN_ATLAS: {
        "url": "https://bhuvan.nrsc.gov.in/bhuvan_links.php",
        "access": "portal -- registration status unclear",
        "auth_required": None,  # UNKNOWN until reconnaissance
        "format": "WMS / Shapefile",
        "license": "UNKNOWN -- verify with ISRO before use",
        "m0_action": "Manually visit portal; determine if shapefile download is available without institutional account",
        "blueprint_priority": "supplementary event catalog",
        "india_coverage": "UNKNOWN",
    },
    DataSource.BHUVAN_LULC: {
        "url": "https://bhuvan.nrsc.gov.in/bhuvan_links.php",
        "access": "portal",
        "auth_required": None,
        "format": "Shapefile",
        "license": "UNKNOWN",
        "m0_action": "Check portal for LULC 50K dataset availability",
        "blueprint_priority": "LULC features",
    },
    DataSource.GSI_GEOLOGY: {
        "url": "https://bhukosh.gsi.gov.in/",
        "access": "portal",
        "auth_required": None,
        "format": "Shapefile",
        "license": "UNKNOWN -- must verify GSI terms before use in academic project",
        "m0_action": "Visit Bhukosh portal; check license agreement; download one state geology file",
        "blueprint_priority": "lithology + fault features",
    },
    DataSource.NOAA_GFS: {
        "url": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/",
        "access": "open -- no login",
        "auth_required": False,
        "expected_size_per_cycle_gb": 100.0,
        "format": "GRIB2",
        "license": "NOAA open data",
        "m0_action": "Probe NOMADS; confirm GRIB2 files accessible; note: bulk download is very large -- subset required",
        "blueprint_priority": "optional DLM forecast input",
        "note": "If unavailable, DLM uses 'Simulated Scenario' label (historical percentiles)",
    },
    DataSource.DISTRICT_BOUNDARIES: {
        "url": "https://raw.githubusercontent.com/datameet/maps/master/Districts/",
        "access": "open GitHub",
        "auth_required": False,
        "expected_size_mb": 15.0,
        "format": "GeoJSON",
        "license": "open",
        "m0_action": "Download and inspect district boundary file in reconnaissance",
        "blueprint_priority": "unit of analysis construction",
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def describe_source(source: DataSource) -> dict:
    """
    Print and return a structured summary of a candidate data source.
    Safe to call -- no network requests, no downloads.
    """
    meta = _SOURCE_REGISTRY.get(source, {})
    print(f"\n{'='*68}")
    print(f"  Data Source: {source.value}")
    print(f"{'='*68}")
    for key, val in meta.items():
        print(f"  {key:<32}: {val}")
    print()
    return meta


def list_candidate_sources() -> list[dict]:
    """
    Return all registered candidate data sources as a list of dicts.
    Useful for tabular inspection in reconnaissance notebooks.
    """
    candidates = []
    for src_enum, meta in _SOURCE_REGISTRY.items():
        item = {"key": src_enum.name, "name": src_enum.value}
        item.update(meta)
        candidates.append(item)
    return candidates


def describe_all_sources() -> None:
    """Print summaries for all registered candidate data sources."""
    for source in DataSource:
        describe_source(source)


def compute_sha256(file_path: str | Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 of a file in streaming chunks. Returns hex digest."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def probe_url(
    url: str,
    timeout: int = 15,
    auth: Optional[tuple[str, str]] = None,
) -> dict:
    """
    Send an HTTP HEAD request to check if a URL is reachable.
    Does NOT download any data. Returns a status dict.

    Parameters
    ----------
    url     : URL to probe.
    timeout : Request timeout in seconds.
    auth    : Optional (username, password) tuple for basic auth.

    Returns
    -------
    dict with keys: url, reachable, status_code, content_type,
                    content_length_mb, redirect_url, elapsed_ms
    """
    result: dict = {
        "url": url,
        "reachable": False,
        "status_code": None,
        "content_type": None,
        "content_length_mb": None,
        "redirect_url": None,
        "elapsed_ms": None,
        "error": None,
    }
    try:
        resp = requests.head(url, timeout=timeout, auth=auth, allow_redirects=True)
        result["reachable"] = resp.status_code < 400
        result["status_code"] = resp.status_code
        result["content_type"] = resp.headers.get("Content-Type")
        cl = resp.headers.get("Content-Length")
        if cl:
            result["content_length_mb"] = round(int(cl) / (1024 ** 2), 2)
        result["redirect_url"] = resp.url if resp.url != url else None
        result["elapsed_ms"] = round(resp.elapsed.total_seconds() * 1000, 1)
        logger.info("probe_url: %s -> %d (%s)", url, resp.status_code, resp.reason)
    except requests.exceptions.Timeout:
        result["error"] = "Timeout"
        logger.warning("probe_url: Timeout for %s", url)
    except requests.exceptions.ConnectionError as exc:
        result["error"] = f"ConnectionError: {exc}"
        logger.warning("probe_url: Connection failed for %s -- %s", url, exc)
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
        logger.warning("probe_url: Unexpected error for %s -- %s", url, exc)
    return result


def safe_download(
    url: str,
    dest_path: str | Path,
    expected_sha256: Optional[str] = None,
    expected_size_mb: Optional[float] = None,
    dry_run: bool = True,
    auth: Optional[tuple[str, str]] = None,
    chunk_size: int = 8192,
) -> Path | None:
    """
    Download a single file safely with SHA-256 verification.

    Parameters
    ----------
    url            : Direct download URL.
    dest_path      : Local destination path (file, not directory).
    expected_sha256: Expected SHA-256 hex digest. If None, hash is computed and
                     printed but not validated (so you can record it).
    expected_size_mb: Used only for user information -- printed before download.
    dry_run        : If True (default), describe the download but do NOT execute it.
                     Always start with dry_run=True; set False only after review.
    auth           : Optional (username, password) for basic auth.
    chunk_size     : Streaming chunk size in bytes.

    Returns
    -------
    Path to downloaded file (or None if dry_run=True).

    Raises
    ------
    DownloadAbortedError  : dry_run=True (by design).
    IntegrityError        : SHA-256 mismatch.
    requests.HTTPError    : Non-200 response.
    """
    dest = Path(dest_path)

    # ---- Print what would happen ----
    print(f"\n{'-'*68}")
    print(f"  safe_download: {'DRY RUN -- no data will be transferred' if dry_run else 'LIVE DOWNLOAD'}")
    print(f"  URL         : {url}")
    print(f"  Destination : {dest}")
    print(f"  Expected size: {f'{expected_size_mb:.1f} MB' if expected_size_mb else 'unknown'}")
    print(f"  SHA-256 check: {'yes -- ' + expected_sha256[:12] + '...' if expected_sha256 else 'none (will compute)'}")
    print(f"{'-'*68}\n")

    if dry_run:
        raise DownloadAbortedError(
            "dry_run=True -- no download performed. "
            "Set dry_run=False explicitly after reviewing the details above."
        )

    # ---- Skip if already exists and verified ----
    if dest.exists() and expected_sha256:
        existing_hash = _sha256_file(dest)
        if existing_hash == expected_sha256.lower():
            logger.info("safe_download: %s already exists and SHA-256 matches. Skipping.", dest)
            print(f"  [SKIP] File already exists and SHA-256 verified: {dest}")
            return dest
        else:
            logger.warning(
                "safe_download: %s exists but SHA-256 mismatch -- re-downloading.", dest
            )

    # ---- Download ----
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_suffix(dest.suffix + ".tmp")
    sha256 = hashlib.sha256()

    try:
        with requests.get(url, stream=True, auth=auth, timeout=60) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        sha256.update(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded / total * 100
                            print(f"\r  Downloading... {pct:.1f}%", end="", flush=True)
        print()  # newline after progress

    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    # ---- Rename tmp to final ----
    tmp_path.rename(dest)
    actual_hash = sha256.hexdigest()

    # ---- Verify integrity ----
    if expected_sha256:
        if actual_hash != expected_sha256.lower():
            dest.unlink()
            raise IntegrityError(
                f"SHA-256 mismatch for {dest}.\n"
                f"  Expected: {expected_sha256}\n"
                f"  Actual  : {actual_hash}\n"
                "File deleted. Check download source."
            )
        print(f"  [OK] SHA-256 verified: {actual_hash}")
    else:
        print(f"  [INFO] SHA-256 (record this for future verification): {actual_hash}")

    size_mb = dest.stat().st_size / (1024 ** 2)
    logger.info("Downloaded %s -> %.1f MB, SHA-256: %s", dest, size_mb, actual_hash)
    print(f"  [OK] Downloaded to {dest} ({size_mb:.1f} MB)")
    return dest


def verify_sha256(file_path: str | Path, expected: str) -> bool:
    """
    Verify the SHA-256 hash of an existing file.

    Parameters
    ----------
    file_path : Path to the local file.
    expected  : Expected SHA-256 hex digest.

    Returns
    -------
    True if hash matches. Raises IntegrityError on mismatch.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    actual = _sha256_file(path)
    if actual != expected.lower():
        raise IntegrityError(
            f"SHA-256 mismatch for {path}.\n"
            f"  Expected: {expected}\n"
            f"  Actual  : {actual}"
        )
    print(f"  [OK] SHA-256 verified for {path.name}")
    return True


def log_checksum(file_path: str | Path, report_path: str | Path) -> str:
    """
    Compute SHA-256 of a file and append to a checksum log file.

    Parameters
    ----------
    file_path   : Path to the downloaded file.
    report_path : Path to the checksum log (one line per file, SHA256  PATH format).

    Returns
    -------
    The SHA-256 hex digest string.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    digest = _sha256_file(path)
    log = Path(report_path)
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{digest}  {path.resolve()}\n")
    logger.info("Logged checksum for %s -> %s", path.name, digest[:12])
    return digest


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 of a file in streaming chunks. Returns hex digest."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()
