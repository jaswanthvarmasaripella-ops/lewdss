"""
tests/test_feature_pipeline.py
==============================
Regional Landslide Risk & Emergency Response Decision System -- SIH26001
Blueprint v2.0 * Milestone M1.4

Tests for:
  A. Raster I/O (DEM tiles and CHIRPS crops)
  B. Date-window correctness for rainfall accumulations
  C. Raster alignment and nodata handling
  D. Event-to-pixel extraction accuracy
  E. Feature table schema and validation
  F. Point-in-polygon spatial attribution
  G. DEM coverage gap detection
  H. Integration test with real project data (if available)

Run with:
    python -m pytest tests/test_feature_pipeline.py -v
"""

from __future__ import annotations

import datetime
import gzip
import json
import struct
import tempfile
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.features.raster_io import (
    CHIRPS_CROP_NODATA,
    CHIRPS_CROP_STRIP_OFFSET,
    DEM_NODATA_THRESHOLD,
    DEM_PIXEL_DEG,
    DEMIndex,
    DEMTile,
    chirps_value_at,
    read_chirps_crop,
)
from src.features.feature_pipeline import (
    DISTRICT_REGION,
    RAIN_WINDOWS,
    REGION_SUFFIXES,
    _chirps_crop_path,
    _point_in_ring,
    build_feature_table,
    compute_rainfall_accumulation,
    extract_event_features,
    point_in_geometry,
    validate_feature_table,
)


# ===========================================================================
# Helpers: synthetic raster creation
# ===========================================================================

def _make_dem_tif(
    path: Path,
    origin_lon: float = 76.0,
    origin_lat: float = 11.0,
    ncols: int = 100,
    nrows: int = 100,
    pixel_deg: float = DEM_PIXEL_DEG,
    fill_value: float = 500.0,
) -> Path:
    """Write a minimal GeoTIFF DEM tile readable by PIL."""
    from PIL import Image

    arr = np.full((nrows, ncols), fill_value, dtype=np.float32)
    # Add a slope gradient in the center (guarded for small grids)
    r_start = min(10, nrows - 1)
    r_end = min(90, nrows)
    c_start = min(10, ncols - 1)
    c_end = min(90, ncols)
    for r in range(r_start, r_end):
        for c in range(c_start, c_end):
            arr[r, c] = fill_value + (r - r_start) * 5.0

    im = Image.fromarray(arr, mode="F")

    # Build GeoTIFF tags
    # ModelPixelScaleTag (33550): (dx, dy, 0)
    # ModelTiepointTag (33922): (0, 0, 0, lon, lat, 0)
    im.tag_v2 = {
        33550: (pixel_deg, pixel_deg, 0.0),
        33922: (0.0, 0.0, 0.0, origin_lon, origin_lat, 0.0),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(str(path), tiffinfo=im.tag_v2)
    return path


def _make_chirps_crop_tif(
    path: Path,
    nrows: int = 200,
    ncols: int = 80,
    origin_lon: float = 73.5,
    origin_lat: float = 18.5,
    pixel_deg: float = 0.05,
    fill_value: float = 10.0,
) -> Path:
    """Write a minimal CHIRPS crop TIF using the same format as chirps_downloader.py."""
    arr = np.full((nrows, ncols), fill_value, dtype=np.float32)
    pixel_data = arr.tobytes()

    BYTE_ORDER = b"II"
    MAGIC = struct.pack("<H", 42)

    def short(v):
        return struct.pack("<H", v)

    def long_(v):
        return struct.pack("<I", v)

    def ifd_entry(tag, typ, count, val):
        return (struct.pack("<H", tag) + struct.pack("<H", typ) +
                struct.pack("<I", count) + struct.pack("<I", val))

    def ifd_entry_double_offset(tag, offset, count=1):
        return (struct.pack("<H", tag) + struct.pack("<H", 12) +
                struct.pack("<I", count) + struct.pack("<I", offset))

    N_ENTRIES = 12
    IFD_OFFSET = 8
    IFD_SIZE = 2 + N_ENTRIES * 12 + 4

    extra_offset = IFD_OFFSET + IFD_SIZE
    pixel_scale_offset = extra_offset
    pixel_scale_data = struct.pack("<3d", pixel_deg, pixel_deg, 0.0)

    tiepoint_offset = pixel_scale_offset + 24
    tiepoint_data = struct.pack("<6d", 0.0, 0.0, 0.0, origin_lon, origin_lat, 0.0)

    strip_offset = tiepoint_offset + 48

    ifd = short(N_ENTRIES)
    ifd += ifd_entry(256, 4, 1, ncols)
    ifd += ifd_entry(257, 4, 1, nrows)
    ifd += ifd_entry(258, 3, 1, 32)
    ifd += ifd_entry(259, 3, 1, 1)
    ifd += ifd_entry(262, 3, 1, 1)
    ifd += ifd_entry(278, 4, 1, nrows)
    ifd += ifd_entry(279, 4, 1, len(pixel_data))
    ifd += ifd_entry(284, 3, 1, 1)
    ifd += ifd_entry(324, 4, 1, strip_offset)
    ifd += ifd_entry(339, 3, 1, 3)
    ifd += ifd_entry_double_offset(33550, pixel_scale_offset, 3)
    ifd += ifd_entry_double_offset(33922, tiepoint_offset, 6)
    ifd += long_(0)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(BYTE_ORDER)
        f.write(MAGIC)
        f.write(long_(IFD_OFFSET))
        f.write(ifd)
        f.write(pixel_scale_data)
        f.write(tiepoint_data)
        f.write(pixel_data)

    return path


def _make_sample_district_geojson(path: Path) -> Path:
    """Write a simple rectangular polygon for testing."""
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"target_district": "TestDistrict", "target_state": "TestState"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [76.0, 10.5], [76.5, 10.5], [76.5, 11.0],
                            [76.0, 11.0], [76.0, 10.5],
                        ]
                    ],
                },
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(geojson, f)
    return path


# ===========================================================================
# A. Raster I/O
# ===========================================================================

class TestDEMTile:

    def test_m14_dem_tile_loads_and_has_correct_extent(self, tmp_path):
        """DEM tile loads via Pillow and reports correct spatial extent."""
        tif_path = _make_dem_tif(
            tmp_path / "test_dem.tif",
            origin_lon=76.0, origin_lat=11.0,
            ncols=100, nrows=100,
        )
        tile = DEMTile(tif_path)
        assert tile.nrows == 100
        assert tile.ncols == 100
        assert abs(tile.min_lon - 76.0) < 1e-6
        assert abs(tile.max_lat - 11.0) < 1e-6
        assert tile.max_lon > tile.min_lon
        assert tile.max_lat > tile.min_lat

    def test_m14_dem_tile_contains_point_inside(self, tmp_path):
        tif_path = _make_dem_tif(tmp_path / "dem.tif", origin_lon=76.0, origin_lat=11.0)
        tile = DEMTile(tif_path)
        # Center of the tile
        mid_lon = (tile.min_lon + tile.max_lon) / 2
        mid_lat = (tile.min_lat + tile.max_lat) / 2
        assert tile.contains(mid_lon, mid_lat)

    def test_m14_dem_tile_rejects_point_outside(self, tmp_path):
        tif_path = _make_dem_tif(tmp_path / "dem.tif", origin_lon=76.0, origin_lat=11.0)
        tile = DEMTile(tif_path)
        assert not tile.contains(90.0, 30.0)

    def test_m14_elevation_extraction_returns_float(self, tmp_path):
        tif_path = _make_dem_tif(tmp_path / "dem.tif", fill_value=1200.0)
        tile = DEMTile(tif_path)
        elev = tile.elevation_at(76.001, 10.999)
        assert elev is not None
        assert isinstance(elev, float)
        assert elev > 0

    def test_m14_elevation_outside_returns_none(self, tmp_path):
        tif_path = _make_dem_tif(tmp_path / "dem.tif")
        tile = DEMTile(tif_path)
        assert tile.elevation_at(90.0, 30.0) is None

    def test_m14_slope_extraction_returns_degrees(self, tmp_path):
        tif_path = _make_dem_tif(tmp_path / "dem.tif")
        tile = DEMTile(tif_path)
        # Use a point in the center where there's a gradient
        mid_lon = (tile.min_lon + tile.max_lon) / 2
        mid_lat = (tile.min_lat + tile.max_lat) / 2
        slope = tile.slope_at(mid_lon, mid_lat)
        assert slope is not None
        assert 0.0 <= slope <= 90.0

    def test_m14_slope_edge_pixel_returns_none(self, tmp_path):
        tif_path = _make_dem_tif(tmp_path / "dem.tif", ncols=3, nrows=3)
        tile = DEMTile(tif_path)
        # Corner pixel cannot compute 3x3 window
        slope = tile.slope_at(tile.min_lon + 0.0001, tile.max_lat - 0.0001)
        assert slope is None


class TestDEMIndex:

    def test_m14_index_finds_correct_tile(self, tmp_path):
        """DEMIndex resolves a point to the right tile."""
        t1 = _make_dem_tif(tmp_path / "t1.tif", origin_lon=76.0, origin_lat=11.0)
        t2 = _make_dem_tif(tmp_path / "t2.tif", origin_lon=77.0, origin_lat=11.0)
        idx = DEMIndex([t1, t2])
        # Point inside t1
        assert idx.elevation_at(76.01, 10.99) is not None
        # Point inside t2
        assert idx.elevation_at(77.01, 10.99) is not None
        # Point outside both
        assert idx.elevation_at(90.0, 30.0) is None


class TestCHIRPSCropReader:

    def test_m14_read_chirps_crop_returns_correct_shape(self, tmp_path):
        """CHIRPS crop reader parses the minimal TIFF format correctly."""
        tif_path = _make_chirps_crop_tif(
            tmp_path / "crop.tif", nrows=200, ncols=80,
            origin_lon=73.5, origin_lat=18.5, fill_value=5.0,
        )
        arr, ox, oy, pdeg = read_chirps_crop(tif_path)
        assert arr.shape == (200, 80)
        assert abs(ox - 73.5) < 1e-6
        assert abs(oy - 18.5) < 1e-6
        assert abs(pdeg - 0.05) < 1e-6
        assert np.allclose(arr, 5.0)

    def test_m14_chirps_value_at_inside(self, tmp_path):
        tif_path = _make_chirps_crop_tif(
            tmp_path / "crop.tif", fill_value=12.5,
            origin_lon=73.5, origin_lat=18.5,
        )
        arr, ox, oy, pdeg = read_chirps_crop(tif_path)
        val = chirps_value_at(arr, ox, oy, pdeg, 75.0, 15.0)
        assert val is not None
        assert abs(val - 12.5) < 1e-6

    def test_m14_chirps_value_at_outside(self, tmp_path):
        tif_path = _make_chirps_crop_tif(tmp_path / "crop.tif")
        arr, ox, oy, pdeg = read_chirps_crop(tif_path)
        val = chirps_value_at(arr, ox, oy, pdeg, 90.0, 30.0)
        assert val is None

    def test_m14_chirps_nodata_returns_none(self, tmp_path):
        tif_path = _make_chirps_crop_tif(
            tmp_path / "crop.tif", fill_value=CHIRPS_CROP_NODATA,
        )
        arr, ox, oy, pdeg = read_chirps_crop(tif_path)
        val = chirps_value_at(arr, ox, oy, pdeg, 75.0, 15.0)
        assert val is None


# ===========================================================================
# B. Date-window correctness
# ===========================================================================

class TestDateWindowCorrectness:

    def test_m14_chirps_crop_path_format(self):
        """CHIRPS crop path construction follows expected naming pattern."""
        p = _chirps_crop_path(Path("/data"), "2018-08-15", "_regionA.tif")
        assert p.name == "chirps-v2.0.2018.08.15_regionA.tif"

    def test_m14_chirps_crop_path_slash_date(self):
        """Slash-separated dates are normalized."""
        p = _chirps_crop_path(Path("/data"), "2018/08/15", "_regionA.tif")
        assert p.name == "chirps-v2.0.2018.08.15_regionA.tif"

    def test_m14_rain_3day_window_uses_correct_dates(self, tmp_path):
        """3-day accumulation sums event_date-2, event_date-1, event_date."""
        rain_dir = tmp_path / "rainfall"
        rain_dir.mkdir()
        # Create 3 days of rainfall crops with known values
        for day, val in [(13, 5.0), (14, 10.0), (15, 20.0)]:
            _make_chirps_crop_tif(
                rain_dir / f"chirps-v2.0.2018.08.{day:02d}_regionA.tif",
                fill_value=val,
            )
        total = compute_rainfall_accumulation(
            "2018-08-15", 75.0, 15.0, 3, rain_dir, "_regionA.tif",
        )
        assert total is not None
        assert abs(total - 35.0) < 1e-3

    def test_m14_rain_7day_window_uses_correct_dates(self, tmp_path):
        """7-day accumulation covers event_date-6 to event_date."""
        rain_dir = tmp_path / "rainfall"
        rain_dir.mkdir()
        for day in range(9, 16):  # Aug 9 through Aug 15
            _make_chirps_crop_tif(
                rain_dir / f"chirps-v2.0.2018.08.{day:02d}_regionA.tif",
                fill_value=1.0,
            )
        total = compute_rainfall_accumulation(
            "2018-08-15", 75.0, 15.0, 7, rain_dir, "_regionA.tif",
        )
        assert total is not None
        assert abs(total - 7.0) < 1e-3

    def test_m14_rain_15day_window_uses_correct_dates(self, tmp_path):
        """15-day accumulation covers event_date-14 to event_date."""
        rain_dir = tmp_path / "rainfall"
        rain_dir.mkdir()
        for day in range(1, 16):
            _make_chirps_crop_tif(
                rain_dir / f"chirps-v2.0.2018.08.{day:02d}_regionA.tif",
                fill_value=2.0,
            )
        total = compute_rainfall_accumulation(
            "2018-08-15", 75.0, 15.0, 15, rain_dir, "_regionA.tif",
        )
        assert total is not None
        assert abs(total - 30.0) < 1e-3

    def test_m14_rain_missing_date_returns_none(self, tmp_path):
        """If any date in the window is missing, accumulation returns None."""
        rain_dir = tmp_path / "rainfall"
        rain_dir.mkdir()
        # Only create 2 out of 3 needed days
        for day in [14, 15]:
            _make_chirps_crop_tif(
                rain_dir / f"chirps-v2.0.2018.08.{day:02d}_regionA.tif",
                fill_value=5.0,
            )
        total = compute_rainfall_accumulation(
            "2018-08-15", 75.0, 15.0, 3, rain_dir, "_regionA.tif",
        )
        assert total is None  # Aug 13 is missing

    def test_m14_rain_window_crosses_month_boundary(self, tmp_path):
        """15-day window ending on Aug 5 should start on Jul 22."""
        rain_dir = tmp_path / "rainfall"
        rain_dir.mkdir()
        # Jul 22 to Jul 31 (10 days) + Aug 1 to Aug 5 (5 days) = 15 days
        for d in range(22, 32):
            _make_chirps_crop_tif(
                rain_dir / f"chirps-v2.0.2018.07.{d:02d}_regionA.tif",
                fill_value=3.0,
            )
        for d in range(1, 6):
            _make_chirps_crop_tif(
                rain_dir / f"chirps-v2.0.2018.08.{d:02d}_regionA.tif",
                fill_value=3.0,
            )
        total = compute_rainfall_accumulation(
            "2018-08-05", 75.0, 15.0, 15, rain_dir, "_regionA.tif",
        )
        assert total is not None
        assert abs(total - 45.0) < 1e-3


# ===========================================================================
# C. Raster alignment and nodata handling
# ===========================================================================

class TestRasterAlignment:

    def test_m14_dem_chirps_pixel_size_ratio_documented(self):
        """DEM (0.000278°) and CHIRPS (0.05°) have a 180:1 pixel ratio."""
        ratio = 0.05 / DEM_PIXEL_DEG
        assert abs(ratio - 180.0) < 1.0

    def test_m14_chirps_nodata_clamped_to_zero_in_accumulation(self, tmp_path):
        """Negative rainfall values are clamped to 0 in accumulation."""
        rain_dir = tmp_path / "rainfall"
        rain_dir.mkdir()
        # One day with -0.5 (should be clamped to 0), others normal
        _make_chirps_crop_tif(
            rain_dir / "chirps-v2.0.2018.08.14_regionA.tif", fill_value=-0.5,
        )
        _make_chirps_crop_tif(
            rain_dir / "chirps-v2.0.2018.08.15_regionA.tif", fill_value=10.0,
        )
        total = compute_rainfall_accumulation(
            "2018-08-15", 75.0, 15.0, 2, rain_dir, "_regionA.tif",
        )
        assert total is not None
        assert abs(total - 10.0) < 1e-3  # -0.5 clamped to 0

    def test_m14_dem_nodata_skips_slope_calculation(self, tmp_path):
        """If any 3×3 DEM neighbor is nodata, slope returns None."""
        from PIL import Image

        arr = np.full((10, 10), 500.0, dtype=np.float32)
        arr[5, 5] = DEM_NODATA_THRESHOLD - 1  # mark center as nodata

        im = Image.fromarray(arr, mode="F")
        im.tag_v2 = {
            33550: (DEM_PIXEL_DEG, DEM_PIXEL_DEG, 0.0),
            33922: (0.0, 0.0, 0.0, 76.0, 11.0, 0.0),
        }
        tif = tmp_path / "nodata_dem.tif"
        im.save(str(tif), tiffinfo=im.tag_v2)

        tile = DEMTile(tif)
        lon = 76.0 + 5 * DEM_PIXEL_DEG + DEM_PIXEL_DEG / 2
        lat = 11.0 - 5 * DEM_PIXEL_DEG - DEM_PIXEL_DEG / 2
        slope = tile.slope_at(lon, lat)
        assert slope is None  # center pixel is nodata


# ===========================================================================
# D. Event-to-pixel extraction accuracy
# ===========================================================================

class TestEventToPixelExtraction:

    def test_m14_extract_event_features_complete(self, tmp_path):
        """Full feature extraction produces all expected columns."""
        dem_path = _make_dem_tif(
            tmp_path / "dem.tif", origin_lon=76.0, origin_lat=11.0,
            fill_value=800.0,
        )
        rain_dir = tmp_path / "rainfall"
        rain_dir.mkdir()
        for d in range(1, 16):
            _make_chirps_crop_tif(
                rain_dir / f"chirps-v2.0.2018.08.{d:02d}_regionA.tif",
                fill_value=5.0,
            )
        geojson_path = _make_sample_district_geojson(tmp_path / "districts.geojson")
        with open(geojson_path, "r") as f:
            dist_data = json.load(f)
        dist_geoms = {feat["properties"]["target_district"]: feat["geometry"]
                      for feat in dist_data["features"]}
        dist_bboxes = {"TestDistrict": (76.0, 10.5, 76.5, 11.0)}

        dem_index = DEMIndex([dem_path])
        event = {
            "id": "test001",
            "lon": 76.01,
            "lat": 10.99,
            "start_date": "2018-08-15",
            "district": "TestDistrict",
        }

        # Monkey-patch DISTRICT_REGION for test
        import src.features.feature_pipeline as fp
        original = fp.DISTRICT_REGION.copy()
        fp.DISTRICT_REGION["TestDistrict"] = "Region A (Western Ghats)"
        try:
            feats = extract_event_features(
                event, dem_index, rain_dir, dist_geoms, dist_bboxes,
            )
        finally:
            fp.DISTRICT_REGION.clear()
            fp.DISTRICT_REGION.update(original)

        assert feats["event_id"] == "test001"
        assert feats["elevation_m"] is not None
        assert feats["slope_deg"] is not None
        assert feats["rain_3d_mm"] is not None
        assert feats["rain_7d_mm"] is not None
        assert feats["rain_15d_mm"] is not None
        assert feats["dem_available"] is True
        assert feats["rain_available"] is True
        assert feats["match_type"] == "in_polygon"


# ===========================================================================
# E. Feature table schema and validation
# ===========================================================================

class TestFeatureTableValidation:

    def test_m14_validate_feature_table_schema(self):
        """Feature table validation produces correct keys."""
        df = pd.DataFrame({
            "event_id": ["e1", "e2"],
            "elevation_m": [500.0, None],
            "slope_deg": [15.0, None],
            "rain_3d_mm": [30.0, None],
            "rain_7d_mm": [60.0, None],
            "rain_15d_mm": [120.0, None],
            "dem_available": [True, False],
            "rain_available": [True, False],
            "match_type": ["in_polygon", "text_only"],
            "district": ["Wayanad", "East Sikkim"],
        })
        checks = validate_feature_table(df)
        assert checks["total_events"] == 2
        assert checks["dem_coverage"] == 1
        assert checks["rain_coverage"] == 1
        assert "elevation_min" in checks
        assert "slope_min" in checks
        assert checks["elevation_below_neg50"] == 0
        assert checks["slope_above_85"] == 0
        assert checks["rain_3d_negative"] == 0

    def test_m14_validate_catches_implausible_slopes(self):
        """Slopes above 85° should be flagged."""
        df = pd.DataFrame({
            "elevation_m": [500.0],
            "slope_deg": [89.0],
            "rain_3d_mm": [10.0],
            "rain_7d_mm": [20.0],
            "rain_15d_mm": [50.0],
            "dem_available": [True],
            "rain_available": [True],
            "match_type": ["in_polygon"],
            "district": ["Wayanad"],
        })
        checks = validate_feature_table(df)
        assert checks["slope_above_85"] == 1


# ===========================================================================
# F. Point-in-polygon spatial attribution
# ===========================================================================

class TestPointInPolygon:

    def test_m14_point_inside_polygon(self):
        geom = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
        }
        assert point_in_geometry(5, 5, geom) is True

    def test_m14_point_outside_polygon(self):
        geom = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
        }
        assert point_in_geometry(15, 5, geom) is False

    def test_m14_point_inside_multipolygon(self):
        geom = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[0, 0], [5, 0], [5, 5], [0, 5], [0, 0]]],
                [[[10, 10], [20, 10], [20, 20], [10, 20], [10, 10]]],
            ],
        }
        assert point_in_geometry(3, 3, geom) is True
        assert point_in_geometry(15, 15, geom) is True
        assert point_in_geometry(7, 7, geom) is False

    def test_m14_point_in_polygon_with_hole(self):
        """Point inside a polygon hole should return False."""
        geom = {
            "type": "Polygon",
            "coordinates": [
                [[0, 0], [20, 0], [20, 20], [0, 20], [0, 0]],       # exterior
                [[5, 5], [15, 5], [15, 15], [5, 15], [5, 5]],       # hole
            ],
        }
        assert point_in_geometry(10, 10, geom) is False  # inside hole
        assert point_in_geometry(2, 2, geom) is True     # inside exterior, outside hole


# ===========================================================================
# G. DEM coverage gap detection
# ===========================================================================

class TestDEMCoverageGaps:

    def test_m14_dem_index_reports_none_for_uncovered_point(self, tmp_path):
        """Points outside all DEM tiles get None elevation and slope."""
        t1 = _make_dem_tif(tmp_path / "t1.tif", origin_lon=76.0, origin_lat=11.0)
        idx = DEMIndex([t1])
        # Point far away
        assert idx.elevation_at(90.0, 25.0) is None
        assert idx.slope_at(90.0, 25.0) is None

    def test_m14_feature_extraction_marks_missing_dem(self, tmp_path):
        """Feature extraction with no covering DEM sets dem_available=False."""
        t1 = _make_dem_tif(tmp_path / "t1.tif", origin_lon=76.0, origin_lat=11.0)
        idx = DEMIndex([t1])
        event = {
            "id": "missing_dem",
            "lon": 90.0,
            "lat": 25.0,
            "start_date": "2018-08-15",
            "district": "East Khasi Hills",
        }
        feats = extract_event_features(event, idx, tmp_path, {}, {})
        assert feats["elevation_m"] is None
        assert feats["slope_deg"] is None
        assert feats["dem_available"] is False


# ===========================================================================
# H. Integration test with real project data (conditional)
# ===========================================================================

class TestIntegrationWithRealData:
    """
    These tests only run if the real DEM tiles and CHIRPS crops exist on disk.
    They verify that the pipeline can extract features from actual data.
    """

    _project_root = Path(__file__).resolve().parent.parent
    _dem_tiles = list(_project_root.glob("data/raw/region_*/Copernicus*DEM.tif"))
    _chirps_dir = _project_root / "data" / "raw" / "rainfall"
    _district_geojson = _project_root / "data" / "raw" / "boundaries" / "target_districts.geojson"

    @pytest.mark.skipif(
        not Path(__file__).resolve().parent.parent.joinpath(
            "data/raw/region_a/Copernicus_DSM_COG_10_N10_00_E076_00_DEM.tif"
        ).exists(),
        reason="Real DEM tile not available",
    )
    def test_m14_real_dem_elevation_at_munnar(self):
        """Munnar (77.06°E, 10.09°N) should have elevation > 1000m."""
        tile = DEMTile(
            self._project_root / "data/raw/region_a/Copernicus_DSM_COG_10_N10_00_E077_00_DEM.tif"
        )
        elev = tile.elevation_at(77.06, 10.09)
        assert elev is not None
        assert elev > 1000.0, f"Munnar elevation too low: {elev}"

    @pytest.mark.skipif(
        not Path(__file__).resolve().parent.parent.joinpath(
            "data/raw/rainfall/chirps-v2.0.2018.08.15_regionA.tif"
        ).exists(),
        reason="Real CHIRPS crop not available",
    )
    def test_m14_real_chirps_extraction_at_munnar(self):
        """Rainfall at Munnar on 2018-08-15 should be non-negative."""
        arr, ox, oy, pdeg = read_chirps_crop(
            self._chirps_dir / "chirps-v2.0.2018.08.15_regionA.tif"
        )
        val = chirps_value_at(arr, ox, oy, pdeg, 77.06, 10.09)
        assert val is not None
        assert val >= 0.0

    @pytest.mark.skipif(
        not Path(__file__).resolve().parent.parent.joinpath(
            "data/raw/boundaries/target_districts.geojson"
        ).exists(),
        reason="District GeoJSON not available",
    )
    def test_m14_real_district_polygon_point_in_polygon(self):
        """Verify Munnar falls inside the Idukki polygon."""
        with open(self._district_geojson, "r") as f:
            data = json.load(f)
        for feat in data["features"]:
            if feat["properties"]["target_district"] == "Idukki":
                assert point_in_geometry(77.06, 10.09, feat["geometry"])
                break
        else:
            pytest.fail("Idukki polygon not found")


# ===========================================================================
# I. Phase 1.4 — Geospatial Alignment Audit Tests
# ===========================================================================

class TestGeospatialAlignmentAudit:
    """
    Automated tests for Phase 1.4 geospatial alignment audit.
    Validates CRS consistency, pixel sizes, tile coverage, and
    cross-raster alignment between DEM and CHIRPS datasets.
    """

    _project_root = Path(__file__).resolve().parent.parent

    def test_m14_dem_crs_all_tiles_wgs84(self, tmp_path):
        """All DEM tiles must use WGS84 geographic coordinates (origin within valid lon/lat range)."""
        dem_tiles = list(self._project_root.glob("data/raw/region_*/Copernicus*DEM.tif"))
        if not dem_tiles:
            pytest.skip("No DEM tiles available")
        from PIL import Image
        for t in dem_tiles:
            im = Image.open(t)
            tie = im.tag_v2[33922]
            origin_lon, origin_lat = tie[3], tie[4]
            # Valid WGS84 geographic range
            assert -180 <= origin_lon <= 180, f"{t.name}: origin_lon={origin_lon} out of WGS84 range"
            assert -90 <= origin_lat <= 90, f"{t.name}: origin_lat={origin_lat} out of WGS84 range"

    def test_m14_dem_pixel_size_consistent_across_tiles(self):
        """All DEM tiles must have identical pixel sizes (1 arcsec = 0.000277778 deg)."""
        dem_tiles = list(self._project_root.glob("data/raw/region_*/Copernicus*DEM.tif"))
        if not dem_tiles:
            pytest.skip("No DEM tiles available")
        from PIL import Image
        dx_vals = set()
        dy_vals = set()
        for t in dem_tiles:
            im = Image.open(t)
            scale = im.tag_v2[33550]
            dx_vals.add(round(scale[0], 10))
            dy_vals.add(round(scale[1], 10))
        assert len(dx_vals) == 1, f"Inconsistent dx: {dx_vals}"
        assert len(dy_vals) == 1, f"Inconsistent dy: {dy_vals}"

    def test_m14_dem_grid_dimensions_3600x3600(self):
        """All Copernicus GLO-30 1deg x 1deg tiles must be 3600x3600."""
        dem_tiles = list(self._project_root.glob("data/raw/region_*/Copernicus*DEM.tif"))
        if not dem_tiles:
            pytest.skip("No DEM tiles available")
        from PIL import Image
        for t in dem_tiles:
            im = Image.open(t)
            arr = np.array(im, dtype=np.float32)
            assert arr.shape == (3600, 3600), f"{t.name}: shape={arr.shape}"

    def test_m14_dem_no_nodata_pixels(self):
        """Acquired DEM tiles should have zero nodata pixels (no ocean voids)."""
        dem_tiles = list(self._project_root.glob("data/raw/region_*/Copernicus*DEM.tif"))
        if not dem_tiles:
            pytest.skip("No DEM tiles available")
        from PIL import Image
        for t in dem_tiles:
            im = Image.open(t)
            arr = np.array(im, dtype=np.float32)
            nodata_count = int(np.sum(arr <= -9000.0))
            assert nodata_count == 0, f"{t.name}: {nodata_count} nodata pixels"

    def test_m14_all_11_dem_tiles_acquired(self):
        """All 11 required DEM tiles must be present on disk."""
        required = [
            "Copernicus_DSM_COG_10_N09_00_E076_00_DEM.tif",
            "Copernicus_DSM_COG_10_N09_00_E077_00_DEM.tif",
            "Copernicus_DSM_COG_10_N10_00_E076_00_DEM.tif",
            "Copernicus_DSM_COG_10_N10_00_E077_00_DEM.tif",
            "Copernicus_DSM_COG_10_N11_00_E075_00_DEM.tif",
            "Copernicus_DSM_COG_10_N11_00_E076_00_DEM.tif",
            "Copernicus_DSM_COG_10_N12_00_E075_00_DEM.tif",
            "Copernicus_DSM_COG_10_N12_00_E076_00_DEM.tif",
            "Copernicus_DSM_COG_10_N25_00_E091_00_DEM.tif",
            "Copernicus_DSM_COG_10_N25_00_E092_00_DEM.tif",
            "Copernicus_DSM_COG_10_N27_00_E088_00_DEM.tif",
        ]
        found = set()
        for t in self._project_root.glob("data/raw/region_*/Copernicus*DEM.tif"):
            found.add(t.name)
        missing = [r for r in required if r not in found]
        assert len(missing) == 0, f"Missing DEM tiles: {missing}"

    def test_m14_chirps_crops_1540_dates_both_regions(self):
        """Both Region A and Region B must have exactly 1540 CHIRPS crop dates."""
        rain_dir = self._project_root / "data" / "raw" / "rainfall"
        if not rain_dir.exists():
            pytest.skip("Rainfall directory not found")
        a_dates = set()
        b_dates = set()
        for f in rain_dir.glob("chirps-v2.0.*_regionA.tif"):
            a_dates.add(f.name.replace("chirps-v2.0.", "").replace("_regionA.tif", ""))
        for f in rain_dir.glob("chirps-v2.0.*_regionB.tif"):
            b_dates.add(f.name.replace("chirps-v2.0.", "").replace("_regionB.tif", ""))
        assert len(a_dates) == 1540, f"Region A has {len(a_dates)} dates, expected 1540"
        assert len(b_dates) == 1540, f"Region B has {len(b_dates)} dates, expected 1540"
        assert a_dates == b_dates, "Region A and B date sets differ"

    def test_m14_chirps_crop_dimensions_consistent(self):
        """CHIRPS crops within each region must have consistent dimensions."""
        rain_dir = self._project_root / "data" / "raw" / "rainfall"
        if not rain_dir.exists():
            pytest.skip("Rainfall directory not found")
        import struct as _struct

        for suffix, expected_dims in [("regionA", (200, 80)), ("regionB", (80, 100))]:
            crops = list(rain_dir.glob(f"*_{suffix}.tif"))[:10]
            for c in crops:
                data = c.read_bytes()
                n_entries = _struct.unpack("<H", data[8:10])[0]
                tags = {}
                for i in range(n_entries):
                    off = 10 + i * 12
                    tag, typ, cnt, val = _struct.unpack("<HHII", data[off:off + 12])
                    tags[tag] = (typ, cnt, val)
                ncols = tags[256][2]
                nrows = tags[257][2]
                assert (nrows, ncols) == expected_dims, (
                    f"{c.name}: got ({nrows},{ncols}), expected {expected_dims}"
                )

    def test_m14_chirps_crop_covers_all_region_a_districts(self):
        """Region A CHIRPS crop must fully cover Wayanad, Idukki, Kodagu bboxes."""
        rain_dir = self._project_root / "data" / "raw" / "rainfall"
        if not rain_dir.exists():
            pytest.skip("Rainfall directory not found")
        geojson_path = self._project_root / "data" / "raw" / "boundaries" / "target_districts.geojson"
        if not geojson_path.exists():
            pytest.skip("District GeoJSON not found")

        # Get CHIRPS Region A extent from first crop
        crop = next(rain_dir.glob("*_regionA.tif"), None)
        if crop is None:
            pytest.skip("No Region A crops")
        arr, ox, oy, pdeg = read_chirps_crop(crop)
        nrows, ncols = arr.shape
        chirps_extent = (ox, oy - nrows * pdeg, ox + ncols * pdeg, oy)

        with open(geojson_path, "r") as f:
            data = json.load(f)

        for feat in data["features"]:
            name = feat["properties"]["target_district"]
            if name not in ("Wayanad", "Idukki", "Kodagu"):
                continue
            coords = feat["geometry"]["coordinates"]
            def flatten(c):
                for el in c:
                    if isinstance(el[0], (int, float)):
                        yield el
                    else:
                        yield from flatten(el)
            pts = list(flatten(coords))
            d_min_lon = min(p[0] for p in pts)
            d_max_lon = max(p[0] for p in pts)
            d_min_lat = min(p[1] for p in pts)
            d_max_lat = max(p[1] for p in pts)

            assert chirps_extent[0] <= d_min_lon, f"{name}: CHIRPS min_lon > district min_lon"
            assert chirps_extent[2] >= d_max_lon, f"{name}: CHIRPS max_lon < district max_lon"
            assert chirps_extent[1] <= d_min_lat, f"{name}: CHIRPS min_lat > district min_lat"
            assert chirps_extent[3] >= d_max_lat, f"{name}: CHIRPS max_lat < district max_lat"

    def test_m14_chirps_crop_covers_all_region_b_districts(self):
        """Region B CHIRPS crop must fully cover East Sikkim, West Sikkim, East Khasi Hills bboxes."""
        rain_dir = self._project_root / "data" / "raw" / "rainfall"
        if not rain_dir.exists():
            pytest.skip("Rainfall directory not found")
        geojson_path = self._project_root / "data" / "raw" / "boundaries" / "target_districts.geojson"
        if not geojson_path.exists():
            pytest.skip("District GeoJSON not found")

        crop = next(rain_dir.glob("*_regionB.tif"), None)
        if crop is None:
            pytest.skip("No Region B crops")
        arr, ox, oy, pdeg = read_chirps_crop(crop)
        nrows, ncols = arr.shape
        chirps_extent = (ox, oy - nrows * pdeg, ox + ncols * pdeg, oy)

        with open(geojson_path, "r") as f:
            data = json.load(f)

        for feat in data["features"]:
            name = feat["properties"]["target_district"]
            if name not in ("East Sikkim", "West Sikkim", "East Khasi Hills"):
                continue
            coords = feat["geometry"]["coordinates"]
            def flatten(c):
                for el in c:
                    if isinstance(el[0], (int, float)):
                        yield el
                    else:
                        yield from flatten(el)
            pts = list(flatten(coords))
            d_min_lon = min(p[0] for p in pts)
            d_max_lon = max(p[0] for p in pts)
            d_min_lat = min(p[1] for p in pts)
            d_max_lat = max(p[1] for p in pts)

            assert chirps_extent[0] <= d_min_lon, f"{name}: CHIRPS min_lon > district min_lon"
            assert chirps_extent[2] >= d_max_lon, f"{name}: CHIRPS max_lon < district max_lon"
            assert chirps_extent[1] <= d_min_lat, f"{name}: CHIRPS min_lat > district min_lat"
            assert chirps_extent[3] >= d_max_lat, f"{name}: CHIRPS max_lat < district max_lat"

    def test_m14_dem_pixel_size_ratio_to_chirps(self):
        """DEM:CHIRPS pixel size ratio must be ~180:1."""
        ratio = 0.05 / DEM_PIXEL_DEG
        assert 179 < ratio < 181, f"Unexpected ratio: {ratio}"

    def test_m14_six_district_polygons_present(self):
        """target_districts.geojson must contain exactly 6 district polygons."""
        path = self._project_root / "data" / "raw" / "boundaries" / "target_districts.geojson"
        if not path.exists():
            pytest.skip("GeoJSON not found")
        with open(path, "r") as f:
            data = json.load(f)
        names = [f["properties"]["target_district"] for f in data["features"]]
        assert len(names) == 6
        expected = {"Wayanad", "Idukki", "Kodagu", "East Sikkim", "West Sikkim", "East Khasi Hills"}
        assert set(names) == expected

    @pytest.mark.skipif(
        not Path(__file__).resolve().parent.parent.joinpath(
            "data/raw/region_b/Copernicus_DSM_COG_10_N27_00_E088_00_DEM.tif"
        ).exists(),
        reason="Sikkim DEM tile not available",
    )
    def test_m14_real_dem_gangtok_elevation(self):
        """Gangtok (88.61E, 27.33N) should have elevation > 1000m."""
        tile = DEMTile(
            self._project_root / "data/raw/region_b/Copernicus_DSM_COG_10_N27_00_E088_00_DEM.tif"
        )
        elev = tile.elevation_at(88.61, 27.33)
        assert elev is not None
        assert elev > 1000.0, f"Gangtok elevation too low: {elev}"

    @pytest.mark.skipif(
        not Path(__file__).resolve().parent.parent.joinpath(
            "data/raw/region_b/Copernicus_DSM_COG_10_N25_00_E091_00_DEM.tif"
        ).exists(),
        reason="Meghalaya DEM tile not available",
    )
    def test_m14_real_dem_shillong_elevation(self):
        """Shillong (91.88E, 25.57N) should have elevation > 1000m."""
        tile = DEMTile(
            self._project_root / "data/raw/region_b/Copernicus_DSM_COG_10_N25_00_E091_00_DEM.tif"
        )
        elev = tile.elevation_at(91.88, 25.57)
        assert elev is not None
        assert elev > 1000.0, f"Shillong elevation too low: {elev}"

    def test_m14_dem_tiles_edge_adjacent_not_overlapping(self):
        """DEM tiles share edges but should not truly overlap (no interior overlap)."""
        dem_tiles = list(self._project_root.glob("data/raw/region_*/Copernicus*DEM.tif"))
        if len(dem_tiles) < 2:
            pytest.skip("Need at least 2 DEM tiles")
        from PIL import Image
        extents = []
        for t in dem_tiles:
            im = Image.open(t)
            scale = im.tag_v2[33550]
            tie = im.tag_v2[33922]
            arr = np.array(im, dtype=np.float32)
            nr, nc = arr.shape
            ox, oy = tie[3], tie[4]
            dx, dy = scale[0], scale[1]
            extents.append({
                "name": t.name,
                "min_lon": ox, "max_lon": ox + nc * dx,
                "min_lat": oy - nr * dy, "max_lat": oy,
            })
        # Check that no two tiles have INTERIOR overlap (edges touching is OK)
        for i, a in enumerate(extents):
            for j, b in enumerate(extents):
                if j <= i:
                    continue
                # Tiles are overlapping in interior if the overlap area > 0
                x_overlap = max(0, min(a["max_lon"], b["max_lon"]) - max(a["min_lon"], b["min_lon"]))
                y_overlap = max(0, min(a["max_lat"], b["max_lat"]) - max(a["min_lat"], b["min_lat"]))
                # Edge-touching means overlap area == 0 or one dimension is 0
                # Interior overlap would be > 0 in both dimensions
                interior = x_overlap > 0.001 and y_overlap > 0.001  # > 1 pixel
                assert not interior, (
                    f"{a['name']} and {b['name']} have interior overlap: "
                    f"{x_overlap:.4f} x {y_overlap:.4f} deg"
                )

