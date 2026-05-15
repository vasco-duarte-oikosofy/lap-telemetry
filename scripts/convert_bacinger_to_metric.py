#!/usr/bin/env python3
"""
Convert bacinger/f1-circuits GeoJSON centerline (WGS84 lon/lat) to local metric coordinates.

Barcelona is in UTM zone 31T (EPSG:32631). We'll use a simple UTM projection
to convert lon/lat to local x,y coordinates in meters.

Output format matches our alignment tool's expected input:
{ track_name, points: [{ x, y, w_right, w_left }] }

Widths are estimated at 6m per side (~12m total track width) for F1 track.
"""

import json
import math
import sys
from pathlib import Path

# Barcelona UTM zone 31T parameters
UTM_ZONE = 31
EARTH_RADIUS = 6378137.0  # WGS84 equatorial radius in meters

def utm_zone_from_lon(lon):
    """Determine UTM zone from longitude."""
    return int((lon + 180) / 6) + 1

def latlon_to_utm(lat, lon, zone):
    """
    Convert WGS84 lat/lon to UTM coordinates (simplified Transverse Mercator).
    Returns (easting, northing) in meters.
    
    This is a simplified formula sufficient for our alignment purposes.
    For production use, use pyproj or similar library.
    """
    # Convert to radians
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    
    # Central meridian for this zone
    lon_origin = (zone - 1) * 6 - 180 + 3
    lon_origin_rad = math.radians(lon_origin)
    
    # Simplified Transverse Mercator projection
    # k0 = 0.9996 (UTM scale factor)
    k0 = 0.9996
    
    # Compute using simplified formulas
    # For Barcelona's latitude (~41.5°), this approximation is accurate enough
    x = k0 * EARTH_RADIUS * (lon_rad - lon_origin_rad) * math.cos(lat_rad)
    y = k0 * EARTH_RADIUS * math.log(math.tan(math.pi/4 + lat_rad/2))
    
    # Add false easting (500000m) and adjust for hemisphere
    x += 500000.0
    if lat < 0:
        y += 10000000.0  # Southern hemisphere
    
    return x, y

def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_bacinger_to_metric.py <input.geojson> [output.json]")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix('.json')
    
    # Read GeoJSON
    with open(input_path, 'r') as f:
        geojson = json.load(f)
    
    # Extract LineString coordinates
    feature = geojson['features'][0]
    coords = feature['geometry']['coordinates']  # [[lon, lat], ...]
    
    # Determine UTM zone (should be 31 for Barcelona)
    sample_lon = coords[0][0]
    zone = utm_zone_from_lon(sample_lon)
    print(f"Using UTM zone {zone} for longitude {sample_lon:.4f}")
    
    # Convert all points to UTM
    utm_points = []
    for lon, lat in coords:
        easting, northing = latlon_to_utm(lat, lon, zone)
        utm_points.append({'x': easting, 'y': northing})
    
    # Center the track around origin for easier alignment
    # Compute centroid
    centroid_x = sum(p['x'] for p in utm_points) / len(utm_points)
    centroid_y = sum(p['y'] for p in utm_points) / len(utm_points)
    
    # Translate to origin
    for p in utm_points:
        p['x'] -= centroid_x
        p['y'] -= centroid_y
        # Add estimated widths (6m per side for F1 track)
        p['w_right'] = 6.0
        p['w_left'] = 6.0
    
    # Output in our alignment tool format
    output = {
        'track_name': 'Circuit de Barcelona-Catalunya (bacinger)',
        'source': 'bacinger/f1-circuits es-1991.geojson',
        'coordinate_system': 'utm31t_meters',
        'units': 'meters',
        'width_estimate': 'constant 6m per side (12m total)',
        'points': utm_points
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Converted {len(utm_points)} points")
    print(f"Output written to {output_path}")
    print(f"Sample point (centered): x={utm_points[0]['x']:.2f}, y={utm_points[0]['y']:.2f}")

if __name__ == '__main__':
    main()
