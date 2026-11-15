"""
src/features/raster_io.py
=========================
Regional Landslide Risk & Emergency Response Decision System -- SIH26001
Blueprint v2.0 * Milestone M1.4

Low-level raster I/O helpers for DEM and CHIRPS crops.

These routines avoid rasterio / GDAL by reading GeoTIFF metadata directly
via ``struct`` (CHIRPS crops) or ``PIL`` (Copernicus DEM tiles).  The two
raster families have very different resolutions and spatial extents, so a
unified reader is intentionally **not** provided — the alignment gap is
documented and handled explicitly by the feature pipeline.

Dependencies: numpy, Pillow (PIL) — both already installed.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# DEM reader (Copernicus GLO-30 COG tiles via Pillow)
# ---------------------------------------------------------------------------

# Copernicus DEM nodata sentinel (the tiles acquired have no explicit GDAL_NODATA
# tag, but values ≤ −9000 are treated as ocean / void).
DEM_NODATA_THRESHOLD: float = -9000.0
DEM_PIXEL_DEG: float = 1.0 / 3600  # ≈ 0.000278° ≈ 30.9 m at equator


class DEMTile:
    """
    In-memory representation of a single Copernicus 1°×1° DEM tile.

    Attributes
    ----------
    path      : Path on disk.
    arr       : float32 NumPy array, shape (nrows, ncols).
    origin_x  : Longitude of the left (west) edge of the top-left pixel.
    origin_y  : Latitude of the top (north) edge of the top-left pixel.
    dx, dy    : Pixel widths in degrees (positive, dx = eastward, dy = southward).
    nrows, ncols : Grid dimensions in pixels.
    """

    def __init__(self, tif_path: str | Path) -> None:
        self.path = Path(tif_path)
        im = Image.open(self.path)
        scale = im.tag_v2[33550]   # ModelPixelScaleTag
        tie = im.tag_v2[33922]     # ModelTiepointTag

        self.origin_x: float = tie[3]
        self.origin_y: float = tie[4]
        self.dx: float = scale[0]
        self.dy: float = scale[1]

        self.arr: np.ndarray = np.array(im, dtype=np.float32)
        self.nrows, self.ncols = self.arr.shape

    # Derived properties --------------------------------------------------

    @property
    def min_lon(self) -> float:
        return self.origin_x

    @property
    def max_lon(self) -> float:
        return self.origin_x + self.ncols * self.dx

    @property
    def max_lat(self) -> float:
        return self.origin_y

    @property
    def min_lat(self) -> float:
        return self.origin_y - self.nrows * self.dy

    def contains(self, lon: float, lat: float) -> bool:
        """Return True if the point falls inside the tile extent."""
        return (self.min_lon <= lon < self.max_lon and
                self.min_lat <= lat < self.max_lat)

    def lonlat_to_rowcol(self, lon: float, lat: float) -> Tuple[int, int]:
        """Convert (lon, lat) to (row, col) indices. No bounds checking."""
        col = int((lon - self.origin_x) / self.dx)
        row = int((self.origin_y - lat) / self.dy)
        return row, col

    def elevation_at(self, lon: float, lat: float) -> Optional[float]:
        """Extract elevation (m) at a point, or None if outside / nodata."""
        if not self.contains(lon, lat):
            return None
        row, col = self.lonlat_to_rowcol(lon, lat)
        row = max(0, min(row, self.nrows - 1))
        col = max(0, min(col, self.ncols - 1))
        val = float(self.arr[row, col])
        if val <= DEM_NODATA_THRESHOLD:
            return None
        return val

    def slope_at(self, lon: float, lat: float) -> Optional[float]:
        """
        Compute slope in degrees at a point using Horn's 3×3 method.

        Returns None if the point is outside the tile, on the edge, or
        any of the 3×3 neighbors are nodata.
        """
        if not self.contains(lon, lat):
            return None
        row, col = self.lonlat_to_rowcol(lon, lat)
        if row < 1 or row >= self.nrows - 1 or col < 1 or col >= self.ncols - 1:
            return None  # edge pixel, cannot compute 3×3 window

        win = self.arr[row - 1:row + 2, col - 1:col + 2]
        if np.any(win <= DEM_NODATA_THRESHOLD):
            return None

        # Convert pixel spacing to metres at this latitude
        lat_rad = np.radians(lat)
        dx_m = self.dx * 111_320.0 * np.cos(lat_rad)
        dy_m = self.dy * 110_574.0

        # Horn's method
        dz_dx = ((win[0, 2] + 2 * win[1, 2] + win[2, 2]) -
                 (win[0, 0] + 2 * win[1, 0] + win[2, 0])) / (8.0 * dx_m)
        dz_dy = ((win[0, 0] + 2 * win[0, 1] + win[0, 2]) -
                 (win[2, 0] + 2 * win[2, 1] + win[2, 2])) / (8.0 * dy_m)
        return float(np.degrees(np.arctan(np.sqrt(dz_dx ** 2 + dz_dy ** 2))))

    def zonal_stats_at(
        self, lon: float, lat: float, radius_km: float
    ) -> Dict[str, Optional[float]]:
        """
        Extract multi-scale zonal statistics across a circular buffer of radius_km.

        Returns a dict with keys:
          - slope_max: Maximum Horn's 3x3 slope within buffer (degrees)
          - slope_p90: 90th-percentile slope within buffer (degrees)
          - elev_relief: Elevation relief (max - min) within buffer (m)
          - n_pixels: Number of valid pixels evaluated in buffer
        """
        empty = {"slope_max": None, "slope_p90": None, "elev_relief": None, "n_pixels": 0}
        if not self.contains(lon, lat):
            return empty

        lat_rad = np.radians(lat)
        dx_m = self.dx * 111_320.0 * np.cos(lat_rad)
        dy_m = self.dy * 110_574.0

        r_center, c_center = self.lonlat_to_rowcol(lon, lat)
        rad_cols = int(np.ceil((radius_km * 1000.0) / dx_m))
        rad_rows = int(np.ceil((radius_km * 1000.0) / dy_m))

        r_min = max(1, r_center - rad_rows)
        r_max = min(self.nrows - 2, r_center + rad_rows)
        c_min = max(1, c_center - rad_cols)
        c_max = min(self.ncols - 2, c_center + rad_cols)

        if r_min >= r_max or c_min >= c_max:
            return empty

        # Subarray with 1-pixel border for Horn's slope computation
        sub_arr = self.arr[r_min - 1:r_max + 2, c_min - 1:c_max + 2]

        # Metric distance grid for core pixels [r_min, r_max], [c_min, c_max]
        rows = np.arange(r_min, r_max + 1)
        cols = np.arange(c_min, c_max + 1)
        y_coords = self.origin_y - (rows + 0.5) * self.dy
        x_coords = self.origin_x + (cols + 0.5) * self.dx

        dy_meters = (y_coords - lat)[:, None] * 110_574.0
        dx_meters = (x_coords - lon)[None, :] * 111_320.0 * np.cos(lat_rad)
        dist_sq = dy_meters ** 2 + dx_meters ** 2
        circular_mask = dist_sq <= (radius_km * 1000.0) ** 2

        elev_core = sub_arr[1:-1, 1:-1]
        valid_mask = circular_mask & (elev_core > DEM_NODATA_THRESHOLD)
        n_valid = int(np.sum(valid_mask))

        if n_valid == 0:
            return empty

        elev_valid = elev_core[valid_mask]
        elev_relief = float(np.max(elev_valid) - np.min(elev_valid))

        # Vectorized Horn's slope across sub_arr
        dz_dx = ((sub_arr[:-2, 2:] + 2 * sub_arr[1:-1, 2:] + sub_arr[2:, 2:]) -
                 (sub_arr[:-2, :-2] + 2 * sub_arr[1:-1, :-2] + sub_arr[2:, :-2])) / (8.0 * dx_m)
        dz_dy = ((sub_arr[:-2, :-2] + 2 * sub_arr[:-2, 1:-1] + sub_arr[:-2, 2:]) -
                 (sub_arr[2:, :-2] + 2 * sub_arr[2:, 1:-1] + sub_arr[2:, 2:])) / (8.0 * dy_m)
        slope_sub = np.degrees(np.arctan(np.sqrt(dz_dx ** 2 + dz_dy ** 2)))

        slope_valid = slope_sub[valid_mask]
        slope_max = float(np.max(slope_valid))
        slope_p90 = float(np.percentile(slope_valid, 90.0))

        return {
            "slope_max": slope_max,
            "slope_p90": slope_p90,
            "elev_relief": elev_relief,
            "n_pixels": n_valid,
        }


class DEMIndex:
    """
    Spatial index over multiple DEM tiles.

    Loads all tiles from a list of paths and resolves point queries to the
    correct tile.
    """

    def __init__(self, tile_paths: list[str | Path]) -> None:
        self.tiles: list[DEMTile] = [DEMTile(p) for p in tile_paths]

    def _find_tile(self, lon: float, lat: float) -> Optional[DEMTile]:
        for t in self.tiles:
            if t.contains(lon, lat):
                return t
        return None

    def elevation_at(self, lon: float, lat: float) -> Optional[float]:
        t = self._find_tile(lon, lat)
        return t.elevation_at(lon, lat) if t else None

    def slope_at(self, lon: float, lat: float) -> Optional[float]:
        t = self._find_tile(lon, lat)
        return t.slope_at(lon, lat) if t else None

    def zonal_stats_at(
        self, lon: float, lat: float, radius_km: float
    ) -> Dict[str, Optional[float]]:
        t = self._find_tile(lon, lat)
        if t:
            return t.zonal_stats_at(lon, lat, radius_km)
        return {"slope_max": None, "slope_p90": None, "elev_relief": None, "n_pixels": 0}


# ---------------------------------------------------------------------------
# CHIRPS crop reader (minimal GeoTIFF written by chirps_downloader.py)
# ---------------------------------------------------------------------------

# The minimal TIFF written by _write_minimal_tiff has a fixed structure:
#   Bytes  0–7  : Header  (II, 42, IFD offset = 8)
#   Bytes  8–…  : IFD with 12 entries
#   Byte  230–… : Float32 pixel strip
# Tag layout (verified empirically in reconciliation audit):
#   256 → ImageWidth  (ncols)
#   257 → ImageLength (nrows)
#   324 → StripOffsets (strip_offset)
#   33550 → ModelPixelScaleTag offset
#   33922 → ModelTiepointTag offset

CHIRPS_CROP_STRIP_OFFSET: int = 230  # fixed by _write_minimal_tiff layout
CHIRPS_CROP_NODATA: float = -9999.0


def read_chirps_crop(tif_path: str | Path) -> Tuple[np.ndarray, float, float, float]:
    """
    Read a CHIRPS regional crop ``.tif`` written by chirps_downloader.py.

    Returns
    -------
    (arr, origin_lon, origin_lat, pixel_deg) where:
      arr        : float32 array, shape (nrows, ncols), in mm/day.
      origin_lon : Longitude of the left edge of pixel [0, 0].
      origin_lat : Latitude of the top edge of pixel [0, 0].
      pixel_deg  : Pixel spacing in degrees (0.05° for CHIRPS-2.0).
    """
    data = Path(tif_path).read_bytes()
    _order, _magic, _ifd_off = struct.unpack("<2sHI", data[:8])

    # Parse IFD entries
    n_entries = struct.unpack("<H", data[8:10])[0]
    tags: Dict[int, Tuple[int, int, int]] = {}
    for i in range(n_entries):
        off = 10 + i * 12
        tag, typ, cnt, val = struct.unpack("<HHII", data[off:off + 12])
        tags[tag] = (typ, cnt, val)

    ncols = tags[256][2]
    nrows = tags[257][2]
    strip_off = tags[324][2]

    # Pixel scale
    ps_off = tags[33550][2]
    pixel_deg = struct.unpack("<d", data[ps_off:ps_off + 8])[0]

    # Tiepoint
    tp_off = tags[33922][2]
    _i, _j, _k, origin_lon, origin_lat, _z = struct.unpack(
        "<6d", data[tp_off:tp_off + 48]
    )

    arr = np.frombuffer(
        data[strip_off:strip_off + nrows * ncols * 4],
        dtype=np.float32,
    ).reshape(nrows, ncols)

    return arr, origin_lon, origin_lat, pixel_deg


def chirps_value_at(
    arr: np.ndarray,
    origin_lon: float,
    origin_lat: float,
    pixel_deg: float,
    lon: float,
    lat: float,
) -> Optional[float]:
    """
    Extract rainfall (mm/day) at a single point from a CHIRPS crop array.

    Returns None if the point is outside the crop extent or is nodata.
    """
    nrows, ncols = arr.shape
    col = int((lon - origin_lon) / pixel_deg)
    row = int((origin_lat - lat) / pixel_deg)
    if not (0 <= col < ncols and 0 <= row < nrows):
        return None
    val = float(arr[row, col])
    if val <= CHIRPS_CROP_NODATA + 1.0:  # tolerance for exact -9999
        return None
    return val


def chirps_buffer_mean_at(
    arr: np.ndarray,
    origin_lon: float,
    origin_lat: float,
    pixel_deg: float,
    lon: float,
    lat: float,
    radius_km: float = 3.0,
) -> Optional[float]:
    """
    Compute area-mean rainfall (mm/day) across CHIRPS cells within radius_km.

    Returns None if the central point is outside or all cells in the buffer are nodata.
    """
    nrows, ncols = arr.shape
    col = int((lon - origin_lon) / pixel_deg)
    row = int((origin_lat - lat) / pixel_deg)
    if not (0 <= col < ncols and 0 <= row < nrows):
        return None

    import math
    lat_rad = np.radians(lat)
    vals = []
    # Check 3x3 neighborhood around central cell
    for r in range(max(0, row - 1), min(nrows, row + 2)):
        for c in range(max(0, col - 1), min(ncols, col + 2)):
            cell_lat = origin_lat - (r + 0.5) * pixel_deg
            cell_lon = origin_lon + (c + 0.5) * pixel_deg
            d_km = math.sqrt(
                ((cell_lat - lat) * 110.574) ** 2 +
                ((cell_lon - lon) * 111.320 * math.cos(lat_rad)) ** 2
            )
            if d_km <= radius_km or (r == row and c == col):
                v = float(arr[r, c])
                if v > CHIRPS_CROP_NODATA + 1.0:
                    vals.append(max(0.0, v))

    return float(np.mean(vals)) if vals else None
