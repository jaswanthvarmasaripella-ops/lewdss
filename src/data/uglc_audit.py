"""
src/data/uglc_audit.py
======================
Audit and quality checks for the Unified Global Landslide Catalogue (UGLC)
acquired GeoPackage tiles covering Region A and Region B.

Authoritative source:
Mancino et al. (ESSD 2024 / Zenodo DOI: 10.5281/zenodo.18643456)
"""

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Target district approximate bounding boxes [min_lon, min_lat, max_lon, max_lat]
DISTRICT_BBOXES: Dict[str, Dict[str, Any]] = {
    # Region A: Western Ghats
    "Wayanad": {
        "region": "Region A (Western Ghats)",
        "state": "Kerala",
        "bbox": (75.78, 11.45, 76.45, 11.98),
        "aliases": ["wayanad", "wyanad", "vainad"],
    },
    "Idukki": {
        "region": "Region A (Western Ghats)",
        "state": "Kerala",
        "bbox": (76.60, 9.50, 77.42, 10.35),
        "aliases": ["idukki", "iduki", "munnar"],
    },
    "Kodagu": {
        "region": "Region A (Western Ghats)",
        "state": "Karnataka",
        "bbox": (75.35, 11.93, 76.18, 12.85),
        "aliases": ["kodagu", "coorg", "madikeri"],
    },
    # Region B: Northeast / Himalayas
    "East Sikkim": {
        "region": "Region B (Northeast)",
        "state": "Sikkim",
        "bbox": (88.40, 27.15, 88.85, 27.50),
        "aliases": ["east sikkim", "gangtok", "pakyong"],
    },
    "West Sikkim": {
        "region": "Region B (Northeast)",
        "state": "Sikkim",
        "bbox": (88.00, 27.10, 88.40, 27.55),
        "aliases": ["west sikkim", "gyalshing", "gezing", "pelling"],
    },
    "East Khasi Hills": {
        "region": "Region B (Northeast)",
        "state": "Meghalaya",
        "bbox": (91.30, 25.10, 92.20, 25.75),
        "aliases": ["east khasi hills", "shillong", "cherrapunji", "sohra"],
    },
}

# Regional broad bounding boxes
REGION_BBOXES: Dict[str, Tuple[float, float, float, float]] = {
    "Region A (Western Ghats)": (73.5, 8.5, 77.5, 18.5),
    "Region B (Northeast)": (88.0, 24.5, 93.0, 28.5),
}


def parse_wkt_point(wkt: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """Extract longitude and latitude from WKT string like POINT (lon lat)."""
    if not wkt:
        return None, None
    m = re.search(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", wkt, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except ValueError:
            return None, None
    return None, None


def evaluate_date_precision(date_str: Optional[str]) -> str:
    """Classify date precision: 'day', 'month', 'year', or 'missing'."""
    if not date_str or date_str.strip() in ("", "ND", "None", "-99999"):
        return "missing"
    s = date_str.strip().replace("-", "/")
    parts = s.split("/")
    if len(parts) == 3:
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if y > 1800 and 1 <= m <= 12 and 1 <= d <= 31:
                return "day"
        except ValueError:
            pass
    elif len(parts) == 2:
        try:
            y, m = int(parts[0]), int(parts[1])
            if y > 1800 and 1 <= m <= 12:
                return "month"
        except ValueError:
            pass
    elif len(parts) == 1:
        try:
            y = int(parts[0])
            if y > 1800:
                return "year"
        except ValueError:
            pass
    return "unknown"


def audit_gpkg_file(gpkg_path: Path) -> Dict[str, Any]:
    """Audit a single UGLC GeoPackage tile file."""
    if not gpkg_path.exists():
        return {"error": f"File not found: {gpkg_path}"}

    conn = sqlite3.connect(str(gpkg_path))
    cursor = conn.cursor()

    # Determine feature table name
    cursor.execute("SELECT table_name FROM gpkg_contents WHERE data_type = 'features'")
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "No features table found in gpkg_contents"}
    table_name = row[0]

    # Column inspection
    cursor.execute(f"PRAGMA table_info({table_name})")
    cols = [col[1] for col in cursor.fetchall()]

    # Fetch all records
    cursor.execute(f"SELECT * FROM {table_name}")
    records = cursor.fetchall()
    conn.close()

    total_records = len(records)
    col_idx = {name: i for i, name in enumerate(cols)}

    parsed_events = []
    invalid_coords = 0
    missing_coords = 0

    for rec in records:
        wkt = rec[col_idx["WKT_GEOM"]] if "WKT_GEOM" in col_idx else None
        lon, lat = parse_wkt_point(wkt)
        if lon is None or lat is None:
            missing_coords += 1
            continue
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            invalid_coords += 1
            continue

        country = str(rec[col_idx["COUNTRY"]]) if "COUNTRY" in col_idx and rec[col_idx["COUNTRY"]] else ""
        start_date = str(rec[col_idx["START DATE"]]) if "START DATE" in col_idx and rec[col_idx["START DATE"]] else ""
        end_date = str(rec[col_idx["END DATE"]]) if "END DATE" in col_idx and rec[col_idx["END DATE"]] else ""
        accuracy = rec[col_idx["ACCURACY"]] if "ACCURACY" in col_idx else None
        reliability = rec[col_idx["RELIABILITY"]] if "RELIABILITY" in col_idx else None
        source_catalog = str(rec[col_idx["OLD DATASET"]]) if "OLD DATASET" in col_idx and rec[col_idx["OLD DATASET"]] else ""
        trigger = str(rec[col_idx["PHYSICAL FACTORS"]]) if "PHYSICAL FACTORS" in col_idx and rec[col_idx["PHYSICAL FACTORS"]] else ""
        notes = str(rec[col_idx["NOTES"]]) if "NOTES" in col_idx and rec[col_idx["NOTES"]] else ""
        event_id = str(rec[col_idx["ID"]]) if "ID" in col_idx else str(rec[0])

        date_prec = evaluate_date_precision(start_date)

        parsed_events.append({
            "id": event_id,
            "lon": lon,
            "lat": lat,
            "country": country,
            "start_date": start_date,
            "end_date": end_date,
            "date_precision": date_prec,
            "accuracy": accuracy,
            "reliability": reliability,
            "source": source_catalog,
            "trigger": trigger,
            "notes": notes,
        })

    return {
        "file": gpkg_path.name,
        "path": str(gpkg_path),
        "table_name": table_name,
        "total_records": total_records,
        "valid_coords": len(parsed_events),
        "missing_coords": missing_coords,
        "invalid_coords": invalid_coords,
        "events": parsed_events,
    }


def run_full_uglc_audit(files: List[Path]) -> Dict[str, Any]:
    """Run cross-tile comprehensive audit against all target districts and regions."""
    all_events: List[Dict[str, Any]] = []
    file_summaries = []

    for f in files:
        res = audit_gpkg_file(f)
        if "events" in res:
            all_events.extend(res["events"])
            file_summaries.append({
                "file": res["file"],
                "total_records": res["total_records"],
                "valid_coords": res["valid_coords"],
            })

    total_valid = len(all_events)

    # 1. India filtering
    india_events = [
        e for e in all_events
        if "india" in e["country"].lower()
        or (68.0 <= e["lon"] <= 97.5 and 8.0 <= e["lat"] <= 37.0)
    ]

    # 2. Duplicate detection (exact coordinate match within 0.001 deg and same date)
    seen_keys = set()
    duplicates = []
    unique_events = []
    for e in india_events:
        key = (round(e["lon"], 4), round(e["lat"], 4), e["start_date"])
        if key in seen_keys:
            duplicates.append(e)
        else:
            seen_keys.add(key)
            unique_events.append(e)

    # 3. Regional assignment
    region_counts: Dict[str, List[Dict[str, Any]]] = {
        "Region A (Western Ghats)": [],
        "Region B (Northeast)": [],
        "Other India": [],
    }

    for e in unique_events:
        lon, lat = e["lon"], e["lat"]
        in_region = False
        for reg_name, bbox in REGION_BBOXES.items():
            if bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]:
                region_counts[reg_name].append(e)
                in_region = True
                break
        if not in_region:
            region_counts["Other India"].append(e)

    # 4. District-level assignment
    district_audit: Dict[str, Dict[str, Any]] = {}
    for d_name, d_info in DISTRICT_BBOXES.items():
        min_lon, min_lat, max_lon, max_lat = d_info["bbox"]
        aliases = d_info["aliases"]

        # Spatial bbox match
        spatial_matches = [
            e for e in unique_events
            if min_lon <= e["lon"] <= max_lon and min_lat <= e["lat"] <= max_lat
        ]

        # Text notes match (for events that mention district in description)
        text_matches = [
            e for e in unique_events
            if any(alias in e["notes"].lower() for alias in aliases)
            and e not in spatial_matches
        ]

        combined = spatial_matches + text_matches

        # Date precision breakdown
        day_prec = sum(1 for e in combined if e["date_precision"] == "day")
        month_prec = sum(1 for e in combined if e["date_precision"] == "month")
        year_prec = sum(1 for e in combined if e["date_precision"] == "year")
        missing_prec = sum(1 for e in combined if e["date_precision"] in ("missing", "unknown"))

        # Accuracies
        accuracies = [e["accuracy"] for e in combined if e["accuracy"] is not None and e["accuracy"] > 0]
        sources = list({e["source"] for e in combined if e["source"]})

        district_audit[d_name] = {
            "region": d_info["region"],
            "state": d_info["state"],
            "total_events": len(combined),
            "spatial_bbox_events": len(spatial_matches),
            "text_alias_events": len(text_matches),
            "day_precision_events": day_prec,
            "day_precision_pct": (day_prec / len(combined) * 100.0) if combined else 0.0,
            "month_precision_events": month_prec,
            "year_precision_events": year_prec,
            "missing_date_events": missing_prec,
            "sources": sources,
            "events": combined,
        }

    return {
        "file_summaries": file_summaries,
        "total_parsed": total_valid,
        "india_events": len(india_events),
        "unique_india_events": len(unique_events),
        "duplicates": len(duplicates),
        "region_counts": {k: len(v) for k, v in region_counts.items()},
        "district_audit": district_audit,
    }
