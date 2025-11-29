"""
Test script for the random location generator.
Generates random points following the same criteria as the app,
plots them on a map, and saves as PNG.

Simplified version using only matplotlib (no folium dependency).
"""

import googlemaps
import random
import math
import os
from datetime import datetime
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Load environment variables
load_dotenv()

# Google Maps API key
API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
if not API_KEY:
    raise ValueError("GOOGLE_MAPS_API_KEY not found in environment variables")

gmaps = googlemaps.Client(key=API_KEY)

# Toronto Union Station coordinates
UNION_STATION = {
    'lat': 43.6452,
    'lng': -79.3806
}

# 10 km radius
MAX_RADIUS_KM = 10
MAX_RADIUS_METERS = MAX_RADIUS_KM * 1000


def generate_random_point_in_radius(center_lat, center_lng, radius_meters):
    """
    Generate a random point within a given radius of a center point.
    Uses uniform distribution for more even coverage.
    """
    # Convert radius from meters to degrees (approximate)
    radius_in_degrees = radius_meters / 111320.0

    # Generate random angle and distance
    angle = random.uniform(0, 2 * math.pi)
    # Use square root for uniform distribution
    distance = math.sqrt(random.uniform(0, 1)) * radius_in_degrees

    # Calculate new coordinates
    delta_lat = distance * math.cos(angle)
    delta_lng = distance * math.sin(angle) / math.cos(math.radians(center_lat))

    new_lat = center_lat + delta_lat
    new_lng = center_lng + delta_lng

    return new_lat, new_lng


def is_on_water(destination):
    """
    Check if a destination point is on water (lake, ocean, etc.).
    Returns True if on water, False if on land.
    """
    try:
        # Reverse geocode the location
        result = gmaps.reverse_geocode((destination['lat'], destination['lng']))

        if not result:
            # No result means likely in water or invalid location
            return True

        # Check if the first result indicates water/natural feature
        first_result = result[0]
        types = first_result.get('types', [])
        address_components = first_result.get('address_components', [])

        # If result is "natural_feature" or "park" without street address, likely water
        if 'natural_feature' in types:
            # Check if there's a street address component
            has_street = any('route' in comp.get('types', []) for comp in address_components)
            if not has_street:
                return True

        # Check if formatted address is too generic (indicates water)
        formatted_address = first_result.get('formatted_address', '')

        # If address is just city/province/country without specifics, likely water
        address_parts = [comp for comp in address_components
                        if any(t in comp.get('types', [])
                              for t in ['street_number', 'route'])]

        if not address_parts:
            # No street-level address components, likely water
            return True

        return False

    except Exception as e:
        print(f"Warning: Could not check if on water: {e}")
        return False


def has_ferry_in_route(origin, destination):
    """
    Check if any route to the destination requires a ferry.
    Returns True if ferry is required, False otherwise.
    """
    origin_str = f"{origin['lat']},{origin['lng']}"
    dest_str = f"{destination['lat']},{destination['lng']}"

    # Check driving route for ferry
    try:
        directions = gmaps.directions(
            origin_str,
            dest_str,
            mode='driving',
            departure_time=datetime.now()
        )

        if directions:
            # Check all steps in the route for ferry
            for leg in directions[0]['legs']:
                for step in leg['steps']:
                    # Check if travel mode is ferry
                    if step.get('travel_mode') == 'FERRY':
                        return True
                    # Check if instructions mention ferry
                    if 'ferry' in step.get('html_instructions', '').lower():
                        return True

        return False
    except Exception as e:
        print(f"Warning: Could not check for ferry: {e}")
        return False


def check_all_modes_available(origin, destination):
    """
    Check if all four transport modes are available for the route.
    Returns True if all modes available, False otherwise.
    """
    modes = ['driving', 'transit', 'bicycling', 'walking']
    origin_str = f"{origin['lat']},{origin['lng']}"
    dest_str = f"{destination['lat']},{destination['lng']}"

    for mode in modes:
        try:
            result = gmaps.distance_matrix(
                origins=origin_str,
                destinations=dest_str,
                mode=mode,
                departure_time=datetime.now()
            )

            if result['rows'][0]['elements'][0]['status'] != 'OK':
                return False

        except Exception as e:
            return False

    return True


def generate_valid_locations(num_points=100):
    """
    Generate valid random locations following the app's criteria.
    """
    valid_locations = []
    attempts = 0
    max_attempts = num_points * 50  # Allow more attempts to find valid points

    print(f"Generating {num_points} valid random locations...")
    print(f"Criteria: Within {MAX_RADIUS_KM}km of Union Station")
    print(f"- Not on water")
    print(f"- No ferry routes")
    print(f"- All 4 transport modes available\n")

    while len(valid_locations) < num_points and attempts < max_attempts:
        attempts += 1

        # Generate random point
        dest_lat, dest_lng = generate_random_point_in_radius(
            UNION_STATION['lat'],
            UNION_STATION['lng'],
            MAX_RADIUS_METERS
        )

        destination = {
            'lat': dest_lat,
            'lng': dest_lng
        }

        # Check criteria
        if is_on_water(destination):
            print(f"  Attempt {attempts}: ✗ On water - skipping")
            continue

        if has_ferry_in_route(UNION_STATION, destination):
            print(f"  Attempt {attempts}: ✗ Requires ferry - skipping")
            continue

        if not check_all_modes_available(UNION_STATION, destination):
            print(f"  Attempt {attempts}: ✗ Not all modes available - skipping")
            continue

        # Valid location!
        valid_locations.append(destination)
        print(f"  Attempt {attempts}: ✓ Valid location #{len(valid_locations)} - ({dest_lat:.4f}, {dest_lng:.4f})")

    print(f"\n✓ Generated {len(valid_locations)} valid locations in {attempts} attempts")
    return valid_locations


def create_map_png(locations, png_file='test_locations_map.png'):
    """
    Create a PNG map with all locations marked using matplotlib.
    """
    print(f"\nCreating map with {len(locations)} locations...")

    # Create figure
    fig, ax = plt.subplots(figsize=(20, 16))

    # Calculate bounds
    lats = [loc['lat'] for loc in locations]
    lngs = [loc['lng'] for loc in locations]

    # Add some padding
    lat_range = max(lats) - min(lats)
    lng_range = max(lngs) - min(lngs)
    padding = max(lat_range, lng_range) * 0.15

    ax.set_xlim(min(lngs) - padding, max(lngs) + padding)
    ax.set_ylim(min(lats) - padding, max(lats) + padding)

    # Plot Union Station
    ax.plot(UNION_STATION['lng'], UNION_STATION['lat'], 'r*',
            markersize=30, label='Union Station', zorder=5,
            markeredgecolor='darkred', markeredgewidth=2)

    # Plot radius circle
    circle = patches.Circle(
        (UNION_STATION['lng'], UNION_STATION['lat']),
        MAX_RADIUS_KM / 111.32,  # Convert km to degrees (approximate)
        fill=False,
        edgecolor='blue',
        linewidth=3,
        linestyle='--',
        alpha=0.6,
        label=f'{MAX_RADIUS_KM}km radius'
    )
    ax.add_patch(circle)

    # Plot all locations
    for i, loc in enumerate(locations, 1):
        ax.plot(loc['lng'], loc['lat'], 'go', markersize=10,
                alpha=0.7, zorder=3, markeredgecolor='darkgreen',
                markeredgewidth=1)
        # Add number labels for first 30 points to avoid clutter
        if i <= 30:
            ax.annotate(str(i), (loc['lng'], loc['lat']),
                       fontsize=7, ha='center', va='center',
                       fontweight='bold', color='white',
                       bbox=dict(boxstyle='circle,pad=0.1',
                               facecolor='green', alpha=0.8,
                               edgecolor='darkgreen'))

    ax.set_xlabel('Longitude', fontsize=14, fontweight='bold')
    ax.set_ylabel('Latitude', fontsize=14, fontweight='bold')
    ax.set_title(f'Random Location Generator Test - {len(locations)} Valid Locations\n'
                 f'Toronto ETA Guesser', fontsize=18, fontweight='bold', pad=20)
    ax.legend(loc='upper right', fontsize=12, framealpha=0.9)
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
    ax.set_aspect('equal')

    # Add summary box
    summary_text = (f'✓ Generated {len(locations)} valid locations\n'
                   f'✓ All on land (not water)\n'
                   f'✓ No ferry routes required\n'
                   f'✓ All 4 transport modes available\n'
                   f'  (driving, transit, cycling, walking)')
    ax.text(0.02, 0.98, summary_text,
            transform=ax.transAxes,
            fontsize=12,
            verticalalignment='top',
            bbox=dict(boxstyle='round,pad=1',
                     facecolor='wheat', alpha=0.9,
                     edgecolor='black', linewidth=2),
            family='monospace')

    # Add coordinate info box
    coord_info = (f'Union Station:\n'
                 f'  {UNION_STATION["lat"]:.4f}°N\n'
                 f'  {UNION_STATION["lng"]:.4f}°W')
    ax.text(0.98, 0.02, coord_info,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment='bottom',
            horizontalalignment='right',
            bbox=dict(boxstyle='round,pad=0.5',
                     facecolor='lightblue', alpha=0.8),
            family='monospace')

    plt.tight_layout()
    plt.savefig(png_file, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"✓ PNG map saved to {png_file}")
    return True


def verify_no_water_points(locations):
    """
    Verify that none of the generated points are on water.
    """
    print("\n" + "="*80)
    print("VERIFICATION: Checking all points are not on water...")
    print("="*80)

    water_points = []
    for i, loc in enumerate(locations, 1):
        if is_on_water(loc):
            water_points.append((i, loc))
            print(f"✗ Location #{i} is on water: ({loc['lat']:.4f}, {loc['lng']:.4f})")
        else:
            print(f"✓ Location #{i} is on land")

    print("="*80)

    if water_points:
        print(f"\n⚠️  WARNING: Found {len(water_points)} locations on water!")
        print("These should have been filtered out. This might indicate:")
        print("- API rate limiting causing false positives")
        print("- Edge cases in the is_on_water() detection logic")
        return False
    else:
        print(f"\n✓ SUCCESS: All {len(locations)} locations verified to be on land!")
        return True


if __name__ == '__main__':
    import sys

    # Allow command line argument for number of points
    num_points = int(sys.argv[1]) if len(sys.argv) > 1 else 20

    print("\n" + "="*80)
    print("🧪 RANDOM LOCATION GENERATOR TEST")
    print("="*80)

    # Generate valid locations
    locations = generate_valid_locations(num_points=num_points)

    if not locations:
        print("\n✗ Failed to generate any valid locations!")
        exit(1)

    # Create map PNG
    create_map_png(locations, 'test_locations_map.png')

    # Verify no water points
    verify_no_water_points(locations)

    print("\n" + "="*80)
    print("✓ TEST COMPLETE")
    print("="*80)
    print(f"Generated: {len(locations)} locations")
    print(f"PNG map: test_locations_map.png")
    print("="*80 + "\n")
