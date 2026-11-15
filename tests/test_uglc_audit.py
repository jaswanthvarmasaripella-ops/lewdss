"""
tests/test_uglc_audit.py
========================
Tests for UGLC landslide catalogue parser and audit functions.
"""

from pathlib import Path
import pytest
from src.data.uglc_audit import (
    parse_wkt_point,
    evaluate_date_precision,
    audit_gpkg_file,
    DISTRICT_BBOXES,
    REGION_BBOXES,
)


def test_parse_wkt_point():
    """Verify WKT point coordinate extraction."""
    lon, lat = parse_wkt_point("POINT (76.123 11.456)")
    assert lon == pytest.approx(76.123)
    assert lat == pytest.approx(11.456)

    # Lowercase & spaces
    lon, lat = parse_wkt_point("point(  -120.5   35.2 )")
    assert lon == pytest.approx(-120.5)
    assert lat == pytest.approx(35.2)

    # Invalid / None
    assert parse_wkt_point(None) == (None, None)
    assert parse_wkt_point("INVALID") == (None, None)


def test_evaluate_date_precision():
    """Verify classification of date strings into temporal precision tiers."""
    assert evaluate_date_precision("2018/08/15") == "day"
    assert evaluate_date_precision("2020-07-22") == "day"
    assert evaluate_date_precision("2019/06") == "month"
    assert evaluate_date_precision("2015") == "year"
    assert evaluate_date_precision("") == "missing"
    assert evaluate_date_precision("ND") == "missing"
    assert evaluate_date_precision(None) == "missing"


def test_district_bboxes_configured():
    """Verify all 6 target districts are properly configured."""
    expected = ["Wayanad", "Idukki", "Kodagu", "East Sikkim", "West Sikkim", "East Khasi Hills"]
    for name in expected:
        assert name in DISTRICT_BBOXES
        info = DISTRICT_BBOXES[name]
        min_lon, min_lat, max_lon, max_lat = info["bbox"]
        assert min_lon < max_lon
        assert min_lat < max_lat


def test_audit_tile_11_4_if_present():
    """Verify audit results on downloaded Region A tile (11_4) if present."""
    tile_path = Path("data/raw/region_a/UGLC_point_tile_11_4.gpkg")
    if not tile_path.exists():
        pytest.skip("Tile 11_4 not downloaded yet")

    res = audit_gpkg_file(tile_path)
    assert res["total_records"] == 771
    assert res["valid_coords"] == 771
    assert res["missing_coords"] == 0
    assert res["invalid_coords"] == 0
    assert len(res["events"]) == 771


def test_event_888497_idukki_bbox_and_polygon():
    """
    Verify that UGLC Event 888497 is physically located inside Idukki's bounding box
    and Idukki's polygon, and outside all other five target districts.
    """
    import json
    tile_path = Path("data/raw/region_a/UGLC_point_tile_11_4.gpkg")
    if not tile_path.exists():
        pytest.skip("Tile 11_4 not downloaded yet")

    res = audit_gpkg_file(tile_path)
    ev = next((e for e in res["events"] if e["id"] == "888497"), None)
    assert ev is not None, "Event 888497 not found in tile 11_4"

    lon, lat = ev["lon"], ev["lat"]
    assert pytest.approx(lon, abs=1e-4) == 77.0133
    assert pytest.approx(lat, abs=1e-4) == 9.8738

    # 1. Inside Idukki BBox
    idukki_bbox = DISTRICT_BBOXES["Idukki"]["bbox"]
    assert idukki_bbox[0] <= lon <= idukki_bbox[2]
    assert idukki_bbox[1] <= lat <= idukki_bbox[3]

    # 2. Outside all other district BBoxes
    for d, info in DISTRICT_BBOXES.items():
        if d != "Idukki":
            b = info["bbox"]
            in_b = b[0] <= lon <= b[2] and b[1] <= lat <= b[3]
            assert not in_b, f"Event 888497 unexpectedly inside {d} bbox"

    # 3. Inside Idukki Polygon in target_districts.geojson
    geojson_path = Path("data/raw/boundaries/target_districts.geojson")
    if geojson_path.exists():
        with open(geojson_path, "r", encoding="utf-8") as f:
            gj = json.load(f)

        def in_ring(x, y, ring):
            inside = False
            n = len(ring)
            for i in range(n):
                x1, y1 = ring[i]
                x2, y2 = ring[(i + 1) % n]
                if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
                    inside = not inside
            return inside

        for feat in gj["features"]:
            d_name = feat["properties"]["target_district"]
            geom = feat["geometry"]
            poly_coords = geom["coordinates"]
            if geom["type"] == "Polygon":
                in_poly = in_ring(lon, lat, poly_coords[0]) and not any(in_ring(lon, lat, h) for h in poly_coords[1:])
            elif geom["type"] == "MultiPolygon":
                in_poly = any(in_ring(lon, lat, p[0]) and not any(in_ring(lon, lat, h) for h in p[1:]) for p in poly_coords)
            else:
                in_poly = False

            if d_name == "Idukki":
                assert in_poly, "Event 888497 must be inside Idukki polygon"
            else:
                assert not in_poly, f"Event 888497 must not be inside {d_name} polygon"

