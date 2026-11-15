"""
src/data/chirps_downloader.py
==============================
Regional Landslide Risk & Emergency Response Decision System -- SIH26001
Blueprint v2.0 * Milestone M1

Safe, resumable CHIRPS daily rainfall downloader.

Design guarantees
-----------------
1. **Manifest-driven resume**: A date is skipped only when its manifest entry
   carries ``status = "VALIDATED"`` AND both regional crop files exist on disk
   and pass integrity checks.  The presence or absence of the compressed ``.gz``
   file is never used as a completion signal.

2. **Atomic crop outputs**: Crop files are written to ``{name}.part`` first.
   The final file is created only by an atomic rename after the crop has been
   validated.  A stale ``.part`` from a previous interrupted run is detected
   and removed before the date is retried.

3. **Completion gate**: A date reaches ``VALIDATED`` only when:
   a. The ``.gz`` download passed all three integrity layers (byte-count,
      gzip CRC-32, TIFF magic).
   b. Both ``_regionA.tif`` and ``_regionB.tif`` were written, their SHA-256
      digests were recorded in the manifest, and their ``.part`` temporaries
      were removed by a successful atomic rename.
   c. The manifest entry was durably written with ``status = "VALIDATED"``
      BEFORE the ``.gz`` is deleted.

4. **No real downloads in tests**: Every network and filesystem call is
   injected via the ``downloader`` parameter so tests can substitute mocks.

USAGE POLICY
------------
This module does NOT initiate any download unless explicitly called with
``dry_run=False``.  The manifest generator (``generate_chirps_manifest.py``)
is always safe to run.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# CHIRPS global grid parameters (verified against sample file 2020.08.01)
CHIRPS_NCOLS: int = 7200          # 360° / 0.05°
CHIRPS_NROWS: int = 2000          # 100° (−50° to +50°) / 0.05°
CHIRPS_PIXEL_DEG: float = 0.05
CHIRPS_ORIGIN_LON: float = -180.0  # left edge of pixel (0,0)
CHIRPS_ORIGIN_LAT: float = 50.0    # top edge of pixel (0,0)
CHIRPS_DTYPE: str = "float32"
CHIRPS_NODATA: float = -9999.0

CHIRPS_URL_TEMPLATE: str = (
    "https://data.chc.ucsb.edu/products/CHIRPS-2.0/"
    "global_daily/tifs/p05/{year}/chirps-v2.0.{year}.{month}.{day}.tif.gz"
)

# TIFF little-endian magic bytes
TIFF_MAGIC_LE: bytes = b"II*\x00"
TIFF_MAGIC_BE: bytes = b"MM\x00*"

# Valid manifest statuses (ordered from least to most complete)
STATUSES = ("PENDING", "FAILED", "DOWNLOADED", "CROPPED", "VALIDATED")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DownloadAbortedError(RuntimeError):
    """Raised when dry_run=True prevents an actual download."""


class IntegrityError(RuntimeError):
    """Raised when a file fails an integrity check."""


class CropError(RuntimeError):
    """Raised when a regional crop operation fails."""


# ---------------------------------------------------------------------------
# Manifest entry dataclass
# ---------------------------------------------------------------------------

@dataclass
class ManifestEntry:
    """
    One row in the CHIRPS download manifest.

    status values
    -------------
    PENDING     -- not yet attempted
    FAILED      -- last attempt raised an error (see error_reason)
    DOWNLOADED  -- .gz downloaded and passed all three integrity layers
    CROPPED     -- both regional crops written (crops not yet confirmed valid)
    VALIDATED   -- both crops confirmed valid, checksums recorded, .gz deleted
    """
    date: str                        # ISO-8601 "YYYY-MM-DD"
    filename: str                    # "chirps-v2.0.YYYY.MM.DD.tif.gz"
    url: str                         # full HTTPS URL
    gz_path: str                     # relative path for the .gz file
    region_a_path: str               # relative path for the Region A crop
    region_b_path: str               # relative path for the Region B crop
    expected_size_bytes: Optional[int] = None  # from HTTP HEAD probe, or None
    status: str = "PENDING"
    gz_sha256: Optional[str] = None
    region_a_sha256: Optional[str] = None
    region_b_sha256: Optional[str] = None
    error_reason: Optional[str] = None
    attempt_count: int = 0
    last_updated: Optional[str] = None

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"Invalid status '{self.status}'. Must be one of {STATUSES}.")


# ---------------------------------------------------------------------------
# Manifest I/O  (atomic writes to prevent corruption on crash)
# ---------------------------------------------------------------------------

class CHIRPSManifest:
    """
    Loads and saves the CHIRPS download manifest as a JSON file.

    All saves are atomic: the JSON is written to a ``.tmp`` sibling file
    first, then renamed over the real file.  This means a crash during
    ``save()`` either preserves the previous manifest intact or produces the
    complete new one -- never a half-written file.
    """

    def __init__(self, manifest_path: str | Path) -> None:
        import threading
        self.path = Path(manifest_path)
        self._entries: Dict[str, ManifestEntry] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self) -> "CHIRPSManifest":
        """Load manifest from disk.  Raises FileNotFoundError if absent."""
        if not self.path.exists():
            raise FileNotFoundError(
                f"Manifest not found: {self.path}. "
                "Run 'scratch/generate_chirps_manifest.py' first."
            )
        with self._lock:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._entries = {
                item["date"]: ManifestEntry(**item)
                for item in raw.get("entries", [])
            }
        logger.info("Loaded manifest with %d entries from %s", len(self._entries), self.path)
        return self

    # ------------------------------------------------------------------
    # Saving (atomic)
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Atomically write the manifest to disk with retry backoff for Windows locks."""
        import os
        import threading
        import time

        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "generated_at": _iso_now(),
                "total_dates": len(self._entries),
                "status_counts": self._status_counts(),
                "entries": [asdict(e) for e in self._entries.values()],
            }
            # Use unique per-thread temp filename to prevent filename collisions
            tmp = self.path.with_name(
                f"{self.path.stem}_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}.tmp"
            )
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)

                # Retry replace on Windows with exponential backoff if locked by OneDrive or file indexer
                max_attempts = 10
                for attempt in range(max_attempts):
                    try:
                        tmp.replace(self.path)
                        break
                    except PermissionError:
                        if attempt == max_attempts - 1:
                            raise
                        time.sleep(0.05 * (2 ** attempt))
            except Exception:
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
                raise
            logger.debug("Manifest saved: %s", self.path)

    # ------------------------------------------------------------------
    # Entry access
    # ------------------------------------------------------------------

    def get(self, date: str) -> Optional[ManifestEntry]:
        with self._lock:
            return self._entries.get(date)

    def all_entries(self) -> List[ManifestEntry]:
        with self._lock:
            return list(self._entries.values())

    def update(self, entry: ManifestEntry, *, save: bool = True) -> None:
        """Update an entry in memory and optionally persist immediately."""
        with self._lock:
            entry.last_updated = _iso_now()
            self._entries[entry.date] = entry
            if save:
                self.save()

    def pending_dates(self) -> List[str]:
        """Return dates that still need work, in chronological order."""
        return sorted(
            d for d, e in self._entries.items()
            if e.status != "VALIDATED"
        )

    def _status_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {s: 0 for s in STATUSES}
        for e in self._entries.values():
            counts[e.status] = counts.get(e.status, 0) + 1
        return counts

    def print_summary(self) -> None:
        counts = self._status_counts()
        total = len(self._entries)
        print(f"\n{'='*56}")
        print(f"  CHIRPS Manifest Summary  ({self.path.name})")
        print(f"{'='*56}")
        print(f"  Total dates : {total}")
        for status in STATUSES:
            print(f"  {status:<12}: {counts.get(status, 0)}")
        print(f"{'='*56}\n")

    @classmethod
    def create_new(
        cls,
        manifest_path: str | Path,
        entries: List[ManifestEntry],
    ) -> "CHIRPSManifest":
        """Create a brand-new manifest from a list of entries and save it."""
        m = cls(manifest_path)
        m._entries = {e.date: e for e in entries}
        m.save()
        return m


# ---------------------------------------------------------------------------
# Integrity helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 of a file in streaming chunks. Returns hex digest."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha.update(chunk)
    return sha.hexdigest()


def validate_gz(path: Path) -> None:
    """
    Validate a gzip file by reading the full decompressed stream.

    This triggers the gzip CRC-32 check embedded in the container and
    catches truncated downloads, bit-flips, and incomplete transfers.

    Raises
    ------
    IntegrityError  : File is not a valid gzip archive.
    """
    import zlib
    try:
        with gzip.open(path, "rb") as gz:
            while gz.read(65536):  # stream through; triggers CRC check at EOF
                pass
    except (gzip.BadGzipFile, OSError, EOFError, zlib.error) as exc:
        raise IntegrityError(
            f"Gzip integrity check failed for {path}: {exc}"
        ) from exc


def validate_tiff_magic(gz_path: Path) -> None:
    """
    Verify the 4-byte TIFF magic number from the decompressed stream header.

    Only reads the first 4 bytes of the decompressed stream; does not load
    the full raster into memory.

    Raises
    ------
    IntegrityError : The payload is not a valid TIFF file.
    """
    try:
        with gzip.open(gz_path, "rb") as gz:
            header = gz.read(4)
    except (gzip.BadGzipFile, OSError, EOFError) as exc:
        raise IntegrityError(
            f"Could not read TIFF magic from {gz_path}: {exc}"
        ) from exc
    if header not in (TIFF_MAGIC_LE, TIFF_MAGIC_BE):
        raise IntegrityError(
            f"Payload of {gz_path} is not a valid TIFF "
            f"(magic bytes: {header!r}, expected {TIFF_MAGIC_LE!r} or {TIFF_MAGIC_BE!r})."
        )


def validate_crop_tiff(tif_path: Path) -> None:
    """
    Validate a written crop TIFF by reading its first 4 bytes.

    Raises
    ------
    IntegrityError : File is missing or not a valid TIFF.
    """
    if not tif_path.exists():
        raise IntegrityError(f"Crop file does not exist: {tif_path}")
    with open(tif_path, "rb") as f:
        header = f.read(4)
    if header not in (TIFF_MAGIC_LE, TIFF_MAGIC_BE):
        raise IntegrityError(
            f"Crop file {tif_path} is not a valid TIFF (magic: {header!r})."
        )


# ---------------------------------------------------------------------------
# Coordinate helpers (no rasterio required)
# ---------------------------------------------------------------------------

def _lon_to_col(lon: float) -> int:
    """Convert a longitude (left edge of desired extent) to a CHIRPS column index."""
    return int((lon - CHIRPS_ORIGIN_LON) / CHIRPS_PIXEL_DEG)


def _lat_to_row(lat: float) -> int:
    """Convert a latitude (top edge of desired extent) to a CHIRPS row index."""
    return int((CHIRPS_ORIGIN_LAT - lat) / CHIRPS_PIXEL_DEG)


def _bbox_to_slice(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> tuple[slice, slice]:
    """
    Convert a WGS-84 bounding box to (row_slice, col_slice) for the CHIRPS
    global float32 array shaped (CHIRPS_NROWS, CHIRPS_NCOLS).

    The slices are clipped to the valid grid extents.
    """
    col_start = max(0, _lon_to_col(min_lon))
    col_end   = min(CHIRPS_NCOLS, _lon_to_col(max_lon))
    row_start = max(0, _lat_to_row(max_lat))   # note: max_lat → smaller row index
    row_end   = min(CHIRPS_NROWS, _lat_to_row(min_lat))
    return slice(row_start, row_end), slice(col_start, col_end)


# ---------------------------------------------------------------------------
# Minimal TIFF writer (no rasterio)
# ---------------------------------------------------------------------------

def _write_minimal_tiff(
    out_path: Path,
    data: "numpy.ndarray",  # float32, shape (nrows, ncols)
    min_lon: float,
    max_lat: float,
) -> None:
    """
    Write a minimal GeoTIFF (32-bit float, single band, LZW-free, no-compress).

    The pixel data is stored as a single strip.  Georeference metadata is
    embedded using the GeoTIFF ModelPixelScaleTag (33550) and
    ModelTiepointTag (33922) so that GIS software can correctly place the raster.

    This writer is intentionally minimal -- it only needs to produce files
    that downstream code (rasterio in Phase 1+) can read correctly.

    Parameters
    ----------
    out_path : Destination .tif file path.
    data     : 2-D float32 NumPy array of shape (nrows, ncols).
    min_lon  : Longitude of the left (west) edge of the raster.
    max_lat  : Latitude of the top (north) edge of the raster.
    """
    import numpy as np
    import struct

    nrows, ncols = data.shape
    pixel_data = data.astype(np.float32).tobytes()
    strip_offset_placeholder = 0  # will be patched after computing IFD size

    # ---- Build IFD entries ------------------------------------------------
    # Each IFD entry is 12 bytes: tag(2) + type(2) + count(4) + value/offset(4)
    # Types: SHORT=3, LONG=4, RATIONAL=5, DOUBLE=12
    # Geotiff tags: ModelPixelScale=33550, ModelTiepoint=33922

    BYTE_ORDER = b"II"   # little-endian
    MAGIC = struct.pack("<H", 42)

    def short(v: int) -> bytes:
        return struct.pack("<H", v)

    def long_(v: int) -> bytes:
        return struct.pack("<I", v)

    def ifd_entry(tag: int, typ: int, count: int, value_or_offset: int) -> bytes:
        return (struct.pack("<H", tag) + struct.pack("<H", typ) +
                struct.pack("<I", count) + struct.pack("<I", value_or_offset))

    def ifd_entry_double_offset(tag: int, offset: int, count: int = 1) -> bytes:
        return (struct.pack("<H", tag) + struct.pack("<H", 12) +
                struct.pack("<I", count) + struct.pack("<I", offset))

    # Rational for RATIONAL type: numerator / denominator stored as two LONGs
    # We'll store DOUBLE values for pixel scale and tiepoint (GeoTIFF spec allows DOUBLE)

    # ---- Data layout planning ---------------------------------------------
    # Header: 8 bytes
    # IFD offset pointer in header: points to IFD
    # We place: [header(8)] [IFD + entry data] [strip data]
    # But we need to compute offsets before writing.

    # IFD entries we'll write:
    #  256 ImageWidth  SHORT 1
    #  257 ImageLength SHORT 1
    #  258 BitsPerSample SHORT 1  → 32
    #  259 Compression SHORT 1   → 1 (no compression)
    #  262 PhotometricInterpretation SHORT 1 → 1 (BlackIsZero)
    #  278 RowsPerStrip SHORT 1  → nrows (single strip)
    #  279 StripByteCounts LONG  1  → len(pixel_data)
    #  284 PlanarConfiguration SHORT 1 → 1
    #  339 SampleFormat SHORT 1  → 3 (IEEE floating point)
    #  33550 ModelPixelScaleTag  DOUBLE 3 → [pixel_deg, pixel_deg, 0.0]
    #  33922 ModelTiepointTag    DOUBLE 6 → [0,0,0, min_lon, max_lat, 0]
    #  324 StripOffsets LONG 1   (value = offset to pixel data)

    N_ENTRIES = 12
    IFD_OFFSET = 8  # immediately after the 8-byte TIFF header
    IFD_SIZE = 2 + N_ENTRIES * 12 + 4  # num_entries(2) + entries + next_ifd(4)

    # Extra data area immediately after IFD:
    extra_offset = IFD_OFFSET + IFD_SIZE

    # ModelPixelScaleTag: 3 doubles = 24 bytes
    pixel_scale_offset = extra_offset
    pixel_scale_data = struct.pack("<3d", CHIRPS_PIXEL_DEG, CHIRPS_PIXEL_DEG, 0.0)

    # ModelTiepointTag: 6 doubles = 48 bytes
    tiepoint_offset = pixel_scale_offset + 24
    tiepoint_data = struct.pack("<6d", 0.0, 0.0, 0.0, min_lon, max_lat, 0.0)

    # Strip data
    strip_offset = tiepoint_offset + 48

    # ---- Build IFD --------------------------------------------------------
    ifd = short(N_ENTRIES)
    ifd += ifd_entry(256, 4, 1, ncols)                              # ImageWidth
    ifd += ifd_entry(257, 4, 1, nrows)                              # ImageLength
    ifd += ifd_entry(258, 3, 1, 32)                                 # BitsPerSample
    ifd += ifd_entry(259, 3, 1, 1)                                  # Compression=none
    ifd += ifd_entry(262, 3, 1, 1)                                  # PhotometricInterp
    ifd += ifd_entry(278, 4, 1, nrows)                              # RowsPerStrip
    ifd += ifd_entry(279, 4, 1, len(pixel_data))                   # StripByteCounts
    ifd += ifd_entry(284, 3, 1, 1)                                  # PlanarConfig
    ifd += ifd_entry(324, 4, 1, strip_offset)                       # StripOffsets
    ifd += ifd_entry(339, 3, 1, 3)                                  # SampleFormat=float
    ifd += ifd_entry_double_offset(33550, pixel_scale_offset, 3)   # ModelPixelScale
    ifd += ifd_entry_double_offset(33922, tiepoint_offset, 6)      # ModelTiepoint
    ifd += long_(0)                                                  # next IFD = none

    # ---- Write file -------------------------------------------------------
    with open(out_path, "wb") as f:
        f.write(BYTE_ORDER)
        f.write(MAGIC)
        f.write(long_(IFD_OFFSET))   # pointer to IFD
        f.write(ifd)
        f.write(pixel_scale_data)
        f.write(tiepoint_data)
        f.write(pixel_data)


# ---------------------------------------------------------------------------
# Crop operation
# ---------------------------------------------------------------------------

def crop_to_region(
    gz_path: Path,
    out_path: Path,
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> None:
    """
    Decompress a CHIRPS ``.tif.gz`` file and write a regional crop.

    The output is written atomically:
      1. Crop is written to ``{out_path}.part``.
      2. Written file is validated (TIFF magic check).
      3. ``.part`` file is renamed to ``out_path``.
      4. Any pre-existing stale ``.part`` from a previous run is removed
         before the crop begins.

    Parameters
    ----------
    gz_path  : Path to the source ``.tif.gz`` file.
    out_path : Final destination path for the cropped ``.tif``.
    min_lon, min_lat, max_lon, max_lat : Bounding box in WGS-84 degrees.

    Raises
    ------
    CropError       : The crop produced a zero-size array or the TIFF write failed.
    IntegrityError  : The written ``.part`` file is not a valid TIFF.
    """
    import numpy as np

    part_path = out_path.with_suffix(".tif.part")

    # Remove any stale .part from a previous interrupted run
    if part_path.exists():
        logger.warning("Removing stale .part file: %s", part_path)
        part_path.unlink()

    # ---- Decompress and slice ----
    row_sl, col_sl = _bbox_to_slice(min_lon, min_lat, max_lon, max_lat)

    try:
        with gzip.open(gz_path, "rb") as gz:
            raw = gz.read()
    except (gzip.BadGzipFile, OSError, EOFError) as exc:
        raise CropError(f"Failed to decompress {gz_path}: {exc}") from exc

    try:
        arr = np.frombuffer(raw[: CHIRPS_NCOLS * CHIRPS_NROWS * 4], dtype=np.float32)
        arr = arr.reshape(CHIRPS_NROWS, CHIRPS_NCOLS)
    except (ValueError, TypeError) as exc:
        raise CropError(f"Failed to reshape CHIRPS array from {gz_path}: {exc}") from exc

    crop = arr[row_sl, col_sl]
    if crop.size == 0:
        raise CropError(
            f"Crop of {gz_path} for bbox [{min_lon},{min_lat},{max_lon},{max_lat}] "
            "produced an empty array. Check bounding box values."
        )

    # ---- Write to .part ----
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _write_minimal_tiff(part_path, crop, min_lon=min_lon, max_lat=max_lat)
    except Exception as exc:
        if part_path.exists():
            part_path.unlink()
        raise CropError(f"Failed to write crop to {part_path}: {exc}") from exc

    # ---- Validate .part before rename ----
    try:
        validate_crop_tiff(part_path)
    except IntegrityError:
        part_path.unlink()
        raise

    # ---- Atomic rename ----
    part_path.replace(out_path)
    logger.info("Crop written: %s (%d bytes)", out_path, out_path.stat().st_size)


# ---------------------------------------------------------------------------
# Resume / skip logic
# ---------------------------------------------------------------------------

def is_date_validated(
    entry: ManifestEntry,
    project_root: Path,
) -> bool:
    """
    Return True only if the manifest entry is VALIDATED, both regional
    crop files exist on disk, pass TIFF integrity checks, and match their
    recorded SHA-256 checksums in the manifest.

    The presence of the ``.gz`` file is intentionally ignored here.

    Parameters
    ----------
    entry        : The manifest entry for this date.
    project_root : Absolute path to the project root (for resolving relative paths).

    Returns
    -------
    bool : True -> safe to skip.  False -> date needs work.
    """
    if entry.status != "VALIDATED":
        return False

    if not entry.region_a_sha256 or not entry.region_b_sha256:
        logger.warning(
            "Manifest says VALIDATED but recorded checksums are missing for %s. "
            "Will re-process.",
            entry.date,
        )
        return False

    a_path = project_root / entry.region_a_path
    b_path = project_root / entry.region_b_path

    if not a_path.exists() or not b_path.exists():
        logger.warning(
            "Manifest says VALIDATED but crop file missing for %s. "
            "Will re-process.",
            entry.date,
        )
        return False

    try:
        validate_crop_tiff(a_path)
        validate_crop_tiff(b_path)
    except IntegrityError as exc:
        logger.warning(
            "Manifest says VALIDATED but crop integrity check failed for %s: %s. "
            "Will re-process.",
            entry.date,
            exc,
        )
        return False

    actual_a = _sha256_file(a_path)
    if actual_a != entry.region_a_sha256:
        logger.warning(
            "Manifest checksum mismatch for Region A crop on %s: expected %s, got %s. "
            "Will re-process.",
            entry.date,
            entry.region_a_sha256,
            actual_a,
        )
        return False

    actual_b = _sha256_file(b_path)
    if actual_b != entry.region_b_sha256:
        logger.warning(
            "Manifest checksum mismatch for Region B crop on %s: expected %s, got %s. "
            "Will re-process.",
            entry.date,
            entry.region_b_sha256,
            actual_b,
        )
        return False

    return True


# ---------------------------------------------------------------------------
# Per-date download + process pipeline
# ---------------------------------------------------------------------------

def process_date(
    entry: ManifestEntry,
    manifest: CHIRPSManifest,
    project_root: Path,
    region_a_bbox: tuple[float, float, float, float],
    region_b_bbox: tuple[float, float, float, float],
    *,
    dry_run: bool = True,
    http_get: Optional[Callable] = None,
    chunk_size: int = 8192,
) -> ManifestEntry:
    """
    Download, validate, crop, and mark a single date complete.

    This is the core pipeline step.  It enforces the completion gate:
    the date reaches ``VALIDATED`` only after both crops are confirmed valid
    and the manifest is saved -- BEFORE the ``.gz`` is deleted.

    Parameters
    ----------
    entry         : Manifest entry for this date (status may be PENDING or FAILED).
    manifest      : Loaded CHIRPSManifest (will be updated after each stage).
    project_root  : Absolute path to the project root.
    region_a_bbox : (min_lon, min_lat, max_lon, max_lat) for Region A.
    region_b_bbox : (min_lon, min_lat, max_lon, max_lat) for Region B.
    dry_run       : If True, describe the action but do NOT perform it.
    http_get      : Callable with the same signature as ``requests.get``.
                    Defaults to ``requests.get``; inject a mock in tests.
    chunk_size    : Download chunk size in bytes.

    Returns
    -------
    The updated ManifestEntry (caller should not re-read from disk).
    """
    if http_get is None:
        http_get = requests.get

    if dry_run:
        logger.info("[DRY RUN] Would process %s", entry.date)
        return entry

    gz_path   = project_root / entry.gz_path
    a_path    = project_root / entry.region_a_path
    b_path    = project_root / entry.region_b_path
    a_part    = a_path.with_suffix(".tif.part")
    b_part    = b_path.with_suffix(".tif.part")
    gz_part   = gz_path.with_suffix(".gz.part")

    entry.attempt_count += 1

    # ===== STAGE 1: Download ==============================================
    # Skip download if .gz is already on disk with a good checksum (meaning
    # a previous run downloaded it but crashed before cropping).
    gz_already_valid = False
    if gz_path.exists() and entry.gz_sha256:
        actual = _sha256_file(gz_path)
        if actual == entry.gz_sha256:
            gz_already_valid = True
            logger.info("STAGE 1 SKIP: %s already on disk and SHA-256 matches.", gz_path.name)

    if not gz_already_valid:
        # Remove stale .gz.part from a previous interrupted download
        if gz_part.exists():
            logger.warning("Removing stale download temp: %s", gz_part)
            gz_part.unlink()

        gz_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with http_get(entry.url, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                content_length = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                sha = hashlib.sha256()
                with open(gz_part, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            sha.update(chunk)
                            downloaded += len(chunk)

            # Layer 1: byte-count check
            if content_length and downloaded != content_length:
                gz_part.unlink()
                raise IntegrityError(
                    f"Size mismatch for {entry.filename}: "
                    f"expected {content_length}, got {downloaded}."
                )

            gz_part.replace(gz_path)
            gz_sha256 = sha.hexdigest()

        except IntegrityError as exc:
            # SIZE_MISMATCH: .part already deleted before the raise
            entry.status = "FAILED"
            entry.error_reason = str(exc)
            manifest.update(entry)
            logger.error("Download integrity check failed for %s: %s", entry.date, exc)
            return entry
        except Exception as exc:
            if gz_part.exists():
                gz_part.unlink()
            entry.status = "FAILED"
            entry.error_reason = f"DOWNLOAD_ERROR: {exc}"
            manifest.update(entry)
            logger.error("Download failed for %s: %s", entry.date, exc)
            return entry

        # Layer 2: gzip CRC-32
        try:
            validate_gz(gz_path)
        except IntegrityError as exc:
            gz_path.unlink()
            entry.status = "FAILED"
            entry.error_reason = f"GZIP_CORRUPT: {exc}"
            manifest.update(entry)
            logger.error("Gzip validation failed for %s: %s", entry.date, exc)
            return entry

        # Layer 3: TIFF magic
        try:
            validate_tiff_magic(gz_path)
        except IntegrityError as exc:
            # Retain the file for inspection per §14.3.5 rule for NOT_GEOTIFF
            entry.status = "FAILED"
            entry.error_reason = f"NOT_GEOTIFF: {exc}"
            manifest.update(entry)
            logger.error("TIFF magic check failed for %s: %s", entry.date, exc)
            return entry

        entry.gz_sha256 = gz_sha256
        entry.status = "DOWNLOADED"
        manifest.update(entry)
        logger.info("STAGE 1 DONE: %s downloaded and validated.", entry.filename)

    # ===== STAGE 2: Crop ==================================================
    # Remove stale .part files from a previous interrupted crop run
    for p in (a_part, b_part):
        if p.exists():
            logger.warning("Removing stale crop temp: %s", p)
            p.unlink()

    try:
        crop_to_region(gz_path, a_path, *region_a_bbox)
        crop_to_region(gz_path, b_path, *region_b_bbox)
    except (CropError, IntegrityError) as exc:
        entry.status = "FAILED"
        entry.error_reason = f"CROP_ERROR: {exc}"
        manifest.update(entry)
        logger.error("Crop failed for %s: %s", entry.date, exc)
        return entry

    entry.status = "CROPPED"
    manifest.update(entry)

    # ===== STAGE 3: Validate crops and record checksums ===================
    try:
        validate_crop_tiff(a_path)
        validate_crop_tiff(b_path)
    except IntegrityError as exc:
        entry.status = "FAILED"
        entry.error_reason = f"CROP_VALIDATION_FAILED: {exc}"
        manifest.update(entry)
        logger.error("Crop validation failed for %s: %s", entry.date, exc)
        return entry

    entry.region_a_sha256 = _sha256_file(a_path)
    entry.region_b_sha256 = _sha256_file(b_path)

    # ===== STAGE 4: Completion gate =======================================
    # Mark VALIDATED and persist BEFORE deleting the .gz.
    entry.status = "VALIDATED"
    entry.error_reason = None
    manifest.update(entry)          # <- durable write; crash here → .gz survives
    logger.info("STAGE 4: %s VALIDATED. Deleting .gz.", entry.filename)

    # Only now delete the compressed source
    if gz_path.exists():
        gz_path.unlink()

    logger.info(
        "COMPLETE: %s → A=%s... B=%s...",
        entry.date,
        (entry.region_a_sha256 or "")[:12],
        (entry.region_b_sha256 or "")[:12],
    )
    return entry


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_chirps_pipeline(
    manifest_path: str | Path,
    project_root: str | Path,
    config: dict,
    *,
    dry_run: bool = True,
    http_get: Optional[Callable] = None,
    max_retries: int = 3,
    workers: int = 1,
) -> dict:
    """
    Resume-safe CHIRPS download-and-crop pipeline.

    Iterates through the manifest in chronological order, skipping any date
    that is already VALIDATED (with both crop files confirmed on disk).
    Failed dates are retried up to ``max_retries`` times per run.

    Parameters
    ----------
    manifest_path : Path to ``chirps_manifest.json``.
    project_root  : Absolute project root (paths in manifest are relative to this).
    config        : Parsed ``config.yaml`` dict; used to read bounding boxes.
    dry_run       : If True, no downloads or writes occur.
    http_get      : Injectable HTTP GET callable (for tests).
    max_retries   : Maximum retry attempts per failed date within this run.
    workers       : Concurrent download threads (default 1).

    Returns
    -------
    dict with keys: total, skipped, completed, failed, errors.
    """
    if dry_run:
        logger.warning("run_chirps_pipeline called with dry_run=True. No data will be downloaded.")

    project_root = Path(project_root)
    manifest = CHIRPSManifest(manifest_path).load()

    # Extract bounding boxes from config
    ra = config["regions"]["region_a"]["bounding_box"]
    rb = config["regions"]["region_b"]["bounding_box"]
    region_a_bbox = (ra["min_lon"], ra["min_lat"], ra["max_lon"], ra["max_lat"])
    region_b_bbox = (rb["min_lon"], rb["min_lat"], rb["max_lon"], rb["max_lat"])

    stats = {"total": 0, "skipped": 0, "completed": 0, "failed": 0, "errors": []}

    if workers > 1 and not dry_run:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        pending_entries = []
        for entry in manifest.all_entries():
            stats["total"] += 1
            if is_date_validated(entry, project_root):
                stats["skipped"] += 1
                logger.debug("SKIP (validated): %s", entry.date)
                continue

            if entry.attempt_count >= max_retries and entry.status == "FAILED":
                logger.warning(
                    "Date %s has hit max_retries (%d). Skipping.", entry.date, max_retries
                )
                stats["failed"] += 1
                stats["errors"].append({"date": entry.date, "reason": entry.error_reason})
                continue

            pending_entries.append(entry)

        total_to_process = len(pending_entries)
        print(f"  [CONCURRENT] Processing {total_to_process} dates using {workers} worker threads...")

        def _worker(ent: ManifestEntry) -> ManifestEntry:
            return process_date(
                entry=ent,
                manifest=manifest,
                project_root=project_root,
                region_a_bbox=region_a_bbox,
                region_b_bbox=region_b_bbox,
                dry_run=dry_run,
                http_get=http_get,
            )

        done_count = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_entry = {executor.submit(_worker, e): e for e in pending_entries}
            for fut in as_completed(future_to_entry):
                done_count += 1
                try:
                    updated = fut.result()
                    if updated.status == "VALIDATED":
                        stats["completed"] += 1
                    else:
                        stats["failed"] += 1
                        stats["errors"].append({"date": updated.date, "reason": updated.error_reason})
                except Exception as exc:
                    ent = future_to_entry[fut]
                    stats["failed"] += 1
                    stats["errors"].append({"date": ent.date, "reason": str(exc)})

                if done_count % 25 == 0 or done_count == total_to_process:
                    print(
                        f"  Progress: {done_count}/{total_to_process} processed "
                        f"({done_count/total_to_process*100:.1f}%) | "
                        f"completed={stats['completed']} failed={stats['failed']} "
                        f"already_skipped={stats['skipped']}"
                    )
    else:
        for entry in manifest.all_entries():
            stats["total"] += 1

            # ---- Resume check: manifest-driven, not .gz-existence-driven ----
            if is_date_validated(entry, project_root):
                stats["skipped"] += 1
                logger.debug("SKIP (validated): %s", entry.date)
                continue

            # ---- Retry limit ----
            if entry.attempt_count >= max_retries and entry.status == "FAILED":
                logger.warning(
                    "Date %s has hit max_retries (%d). Skipping.", entry.date, max_retries
                )
                stats["failed"] += 1
                stats["errors"].append({"date": entry.date, "reason": entry.error_reason})
                continue

            updated = process_date(
                entry=entry,
                manifest=manifest,
                project_root=project_root,
                region_a_bbox=region_a_bbox,
                region_b_bbox=region_b_bbox,
                dry_run=dry_run,
                http_get=http_get,
            )

            if updated.status == "VALIDATED":
                stats["completed"] += 1
            else:
                stats["failed"] += 1
                stats["errors"].append({"date": updated.date, "reason": updated.error_reason})

    manifest.print_summary()
    return stats


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_completion_report(
    manifest_path: str | Path,
    project_root: str | Path,
) -> dict:
    """
    Scan the manifest and produce a structured report distinguishing
    DOWNLOADED / CROPPED / VALIDATED / FAILED / PENDING dates.

    Returns a dict suitable for JSON serialisation or printing.
    """
    project_root = Path(project_root)
    manifest = CHIRPSManifest(manifest_path).load()

    report: dict = {
        "manifest_path": str(manifest_path),
        "generated_at": _iso_now(),
        "totals": {s: 0 for s in STATUSES},
        "disk_state_mismatches": [],
        "failed_dates": [],
        "validated_dates_with_missing_crops": [],
    }

    for entry in manifest.all_entries():
        report["totals"][entry.status] = report["totals"].get(entry.status, 0) + 1

        if entry.status == "FAILED":
            report["failed_dates"].append({
                "date": entry.date,
                "attempts": entry.attempt_count,
                "reason": entry.error_reason,
            })

        if entry.status == "VALIDATED":
            a_ok = (project_root / entry.region_a_path).exists()
            b_ok = (project_root / entry.region_b_path).exists()
            if not (a_ok and b_ok):
                report["validated_dates_with_missing_crops"].append({
                    "date": entry.date,
                    "region_a_missing": not a_ok,
                    "region_b_missing": not b_ok,
                })
            elif not is_date_validated(entry, project_root):
                report["disk_state_mismatches"].append({
                    "date": entry.date,
                    "reason": "Crop integrity failure or SHA-256 checksum mismatch",
                })

    return report


# ---------------------------------------------------------------------------
# Private utilities
# ---------------------------------------------------------------------------

def _iso_now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import yaml

    parser = argparse.ArgumentParser(description="CHIRPS Daily Rainfall Downloader (Step 1.3)")
    parser.add_argument("--manifest", default="scratch/chirps_manifest.json", help="Path to manifest JSON")
    parser.add_argument("--config", default="configs/config.yaml", help="Path to config.yaml")
    parser.add_argument("--workers", type=int, default=4, help="Worker threads for concurrent downloading (default: 4)")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retries per date")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without downloading")
    parser.add_argument("--report", action="store_true", help="Generate and print completion report only")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    _root = Path(__file__).resolve().parent.parent.parent
    _manifest = _root / args.manifest
    _cfg_path = _root / args.config

    with open(_cfg_path, "r", encoding="utf-8") as f:
        _cfg = yaml.safe_load(f)

    if args.report:
        rep = generate_completion_report(_manifest, _root)
        print(json.dumps(rep, indent=2))
    else:
        print(f"\n=======================================================")
        print(f"  CHIRPS Pipeline Launcher (Step 1.3)")
        print(f"  Manifest: {args.manifest}")
        print(f"  Workers : {args.workers}")
        print(f"  Dry run : {args.dry_run}")
        print(f"=======================================================\n")
        stats = run_chirps_pipeline(
            manifest_path=_manifest,
            project_root=_root,
            config=_cfg,
            dry_run=args.dry_run,
            max_retries=args.max_retries,
            workers=args.workers,
        )
        print(f"\nPipeline Run Summary: {stats}")
        rep = generate_completion_report(_manifest, _root)
        print("\nFinal Manifest State:")
        for st, count in rep["totals"].items():
            print(f"  {st:<12}: {count}")
        if rep["failed_dates"]:
            print(f"\nFailed dates ({len(rep['failed_dates'])}):")
            for fd in rep["failed_dates"][:10]:
                print(f"  {fd['date']}: {fd['reason']}")
            if len(rep["failed_dates"]) > 10:
                print(f"  ... and {len(rep['failed_dates']) - 10} more.")

