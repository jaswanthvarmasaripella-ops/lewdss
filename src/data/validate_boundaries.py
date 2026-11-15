import json
from pathlib import Path

TARGET_GEOJSON_PATH = Path("data/raw/boundaries/target_districts.geojson")

def validate_target_districts():
    assert TARGET_GEOJSON_PATH.exists(), f"File not found: {TARGET_GEOJSON_PATH}"
    
    with open(TARGET_GEOJSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data.get("type") == "FeatureCollection", "Top-level must be FeatureCollection"
    features = data.get("features", [])
    assert len(features) == 6, f"Expected 6 features, found {len(features)}"
    
    expected_districts = {
        "Wayanad": {"min_lon": 75.7, "max_lon": 76.5, "min_lat": 11.4, "max_lat": 12.0, "state": "Kerala"},
        "Idukki": {"min_lon": 76.5, "max_lon": 77.5, "min_lat": 9.4, "max_lat": 10.4, "state": "Kerala"},
        "Kodagu": {"min_lon": 75.3, "max_lon": 76.2, "min_lat": 11.9, "max_lat": 12.9, "state": "Karnataka"},
        "East Sikkim": {"min_lon": 88.4, "max_lon": 88.9, "min_lat": 27.1, "max_lat": 27.6, "state": "Sikkim"},
        "West Sikkim": {"min_lon": 88.0, "max_lon": 88.5, "min_lat": 27.0, "max_lat": 27.6, "state": "Sikkim"},
        "East Khasi Hills": {"min_lon": 91.2, "max_lon": 92.2, "min_lat": 25.1, "max_lat": 25.8, "state": "Meghalaya"},
    }
    
    found_districts = {}
    for feat in features:
        props = feat.get("properties", {})
        d_name = props.get("target_district")
        assert d_name in expected_districts, f"Unexpected district: {d_name}"
        geom = feat.get("geometry", {})
        g_type = geom.get("type")
        assert g_type in ("Polygon", "MultiPolygon"), f"Invalid geometry type: {g_type}"
        coords = geom.get("coordinates", [])
        assert len(coords) > 0, f"Empty coordinates for {d_name}"
        
        # Collect all points
        all_pts = []
        if g_type == "Polygon":
            for ring in coords:
                assert len(ring) >= 4, f"Ring must have >= 4 points, got {len(ring)}"
                assert ring[0] == ring[-1], f"Ring must be closed for {d_name}"
                all_pts.extend(ring)
        elif g_type == "MultiPolygon":
            for poly in coords:
                for ring in poly:
                    assert len(ring) >= 4, f"Ring must have >= 4 points, got {len(ring)}"
                    assert ring[0] == ring[-1], f"Ring must be closed for {d_name}"
                    all_pts.extend(ring)
                    
        lons = [p[0] for p in all_pts]
        lats = [p[1] for p in all_pts]
        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)
        
        spec = expected_districts[d_name]
        # Validate that actual bounds intersect nicely with expected bounds
        assert min_lon >= spec["min_lon"] - 0.2, f"{d_name} min_lon {min_lon} < {spec['min_lon'] - 0.2}"
        assert max_lon <= spec["max_lon"] + 0.2, f"{d_name} max_lon {max_lon} > {spec['max_lon'] + 0.2}"
        assert min_lat >= spec["min_lat"] - 0.2, f"{d_name} min_lat {min_lat} < {spec['min_lat'] - 0.2}"
        assert max_lat <= spec["max_lat"] + 0.2, f"{d_name} max_lat {max_lat} > {spec['max_lat'] + 0.2}"
        
        found_districts[d_name] = {
            "state": props.get("target_state"),
            "geometry_type": g_type,
            "total_vertices": len(all_pts),
            "bbox": (round(min_lon, 4), round(min_lat, 4), round(max_lon, 4), round(max_lat, 4)),
            "centroid": (round(sum(lons)/len(lons), 4), round(sum(lats)/len(lats), 4)),
        }
        print(f"[OK] {d_name} ({props.get('target_state')}): {g_type}, {len(all_pts)} vertices, bbox={found_districts[d_name]['bbox']}, centroid={found_districts[d_name]['centroid']}")

    print("\nAll 6 target districts successfully validated!")
    return found_districts

if __name__ == "__main__":
    validate_target_districts()
