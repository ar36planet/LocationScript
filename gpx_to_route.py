#!/usr/bin/env python3
"""Convert a GPX file to the route JSON format used by this project."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

def parse_gpx(gpx_path: str) -> list[tuple[str, str]]:
    tree = ET.parse(gpx_path)
    root = tree.getroot()

    # extract namespace prefix (may be empty string if no namespace declared)
    tag = root.tag
    ns_prefix = ""
    if tag.startswith("{"):
        ns_prefix = tag[:tag.index("}") + 1]

    points: list[tuple[str, str]] = []

    for tag_name in (f"{ns_prefix}trkpt", f"{ns_prefix}wpt", f"{ns_prefix}rtept"):
        for elem in root.iter(tag_name):
            lat = elem.get("lat")
            lon = elem.get("lon")
            if lat and lon:
                points.append((lat, lon))
        if points:
            break

    return points


def to_route_json(points: list[tuple[str, str]], dwell: int = 30) -> list[dict]:
    result = []
    for lat, lon in points:
        # normalise decimal places to 6
        lat_f = f"{float(lat):.6f}"
        lon_f = f"{float(lon):.6f}"
        result.append({
            "name": f"{lat_f}, {lon_f}",
            "lat": lat_f,
            "lng": lon_f,
            "dwell": dwell,
        })
    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Convert GPX to route JSON")
    parser.add_argument("gpx", help="Input .gpx file")
    parser.add_argument("-o", "--output", help="Output .json file (default: same name as gpx)")
    parser.add_argument("--dwell", type=int, default=30, help="Dwell time in seconds (default: 30)")
    args = parser.parse_args()

    gpx_path = Path(args.gpx)
    if not gpx_path.exists():
        print(f"Error: file not found: {gpx_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else gpx_path.with_suffix(".json")

    points = parse_gpx(str(gpx_path))
    if not points:
        print("Error: no track points found in GPX file.", file=sys.stderr)
        sys.exit(1)

    route = to_route_json(points, dwell=args.dwell)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(route, f, ensure_ascii=False, indent=2)

    print(f"Converted {len(route)} points → {output_path}")


if __name__ == "__main__":
    main()
