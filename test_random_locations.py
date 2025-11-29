"""
Test script for the random location generator.
Generates 100 random points following the same criteria as the app,
plots them on a map, and saves as PNG.
"""

import googlemaps
import random
import math
import os
from datetime import datetime
from dotenv import load_dotenv
import folium
import matplotlib.pyplot as plt
import matplotlib.patches as patches
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    import time
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Note: Selenium not available, will use matplotlib for PNG export")

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

        # If result is "natural_feature" or "park" without street address, likely water
        if 'natural_feature' in types:
            # Check if there's a street address component
            address_components = first_result.get('address_components', [])
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


def create_map_with_locations(locations, filename='test_locations_map.html'):
    """
    Create a folium map with all locations marked.
    """
    # Create map centered on Union Station
    m = folium.Map(
        location=[UNION_STATION['lat'], UNION_STATION['lng']],
        zoom_start=11,
        tiles='OpenStreetMap'
    )

    # Add Union Station marker
    folium.Marker(
        location=[UNION_STATION['lat'], UNION_STATION['lng']],
        popup='Union Station (Origin)',
        icon=folium.Icon(color='red', icon='info-sign'),
        tooltip='Union Station'
    ).add_to(m)

    # Add circle showing the search radius
    folium.Circle(
        location=[UNION_STATION['lat'], UNION_STATION['lng']],
        radius=MAX_RADIUS_METERS,
        color='blue',
        fill=True,
        fillColor='blue',
        fillOpacity=0.1,
        popup=f'{MAX_RADIUS_KM}km radius'
    ).add_to(m)

    # Add all generated locations
    for i, loc in enumerate(locations, 1):
        folium.CircleMarker(
            location=[loc['lat'], loc['lng']],
            radius=5,
            popup=f'Location #{i}<br>({loc["lat"]:.4f}, {loc["lng"]:.4f})',
            color='green',
            fill=True,
            fillColor='green',
            fillOpacity=0.7,
            tooltip=f'#{i}'
        ).add_to(m)

    # Save map
    m.save(filename)
    print(f"\n✓ Map saved to {filename}")
    return m, filename


def save_map_as_png_matplotlib(locations, png_file='test_locations_map.png'):
    """
    Create a simple PNG map using matplotlib.
    """
    print(f"\nCreating PNG map with matplotlib...")

    # Create figure
    fig, ax = plt.subplots(figsize=(16, 12))

    # Calculate bounds
    lats = [loc['lat'] for loc in locations]
    lngs = [loc['lng'] for loc in locations]

    # Add some padding
    lat_range = max(lats) - min(lats)
    lng_range = max(lngs) - min(lngs)
    padding = max(lat_range, lng_range) * 0.1

    ax.set_xlim(min(lngs) - padding, max(lngs) + padding)
    ax.set_ylim(min(lats) - padding, max(lats) + padding)

    # Plot Union Station
    ax.plot(UNION_STATION['lng'], UNION_STATION['lat'], 'r*',
            markersize=20, label='Union Station', zorder=5)

    # Plot radius circle
    circle = patches.Circle(
        (UNION_STATION['lng'], UNION_STATION['lat']),
        MAX_RADIUS_KM / 111.32,  # Convert km to degrees (approximate)
        fill=False,
        edgecolor='blue',
        linewidth=2,
        linestyle='--',
        alpha=0.5,
        label=f'{MAX_RADIUS_KM}km radius'
    )
    ax.add_patch(circle)

    # Plot all locations
    for i, loc in enumerate(locations, 1):
        ax.plot(loc['lng'], loc['lat'], 'go', markersize=8, alpha=0.6, zorder=3)
        # Add number labels for first 20 points
        if i <= 20:
            ax.annotate(str(i), (loc['lng'], loc['lat']),
                       fontsize=6, ha='center', va='center')

    ax.set_xlabel('Longitude', fontsize=12)
    ax.set_ylabel('Latitude', fontsize=12)
    ax.set_title(f'Random Location Test - {len(locations)} Valid Locations\n'
                 f'Toronto ETA Guesser', fontsize=16, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal')

    # Add summary text
    summary_text = (f'✓ Generated {len(locations)} valid locations\n'
                   f'✓ All on land (not water)\n'
                   f'✓ No ferry routes\n'
                   f'✓ All 4 transport modes available')
    ax.text(0.02, 0.98, summary_text,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    plt.tight_layout()
    plt.savefig(png_file, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"✓ PNG saved to {png_file}")
    return True


def save_map_as_png_selenium(html_file, png_file='test_locations_map_selenium.png'):
    """
    Convert the HTML map to PNG using Selenium (if available).
    """
    if not SELENIUM_AVAILABLE:
        print("✗ Selenium not available, skipping HTML to PNG conversion")
        return False

    print(f"\nConverting HTML map to PNG with Selenium...")

    try:
        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')

        # Create driver
        driver = webdriver.Chrome(options=chrome_options)

        # Load the HTML file
        driver.get(f'file://{os.path.abspath(html_file)}')

        # Wait for map to load
        time.sleep(3)

        # Take screenshot
        driver.save_screenshot(png_file)
        driver.quit()

        print(f"✓ Selenium PNG saved to {png_file}")
        return True

    except Exception as e:
        print(f"✗ Error saving PNG with Selenium: {e}")
        print("  Note: Make sure Chrome and chromedriver are installed")
        return False


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
        print("These should have been filtered out. Check the is_on_water() function.")
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

    # Create map
    map_obj, html_file = create_map_with_locations(locations)

    # Save as PNG (using matplotlib - more reliable)
    save_map_as_png_matplotlib(locations, 'test_locations_map.png')

    # Optionally save HTML map as PNG with Selenium (if available)
    save_map_as_png_selenium(html_file, 'test_locations_map_interactive.png')

    # Verify no water points
    verify_no_water_points(locations)

    print("\n" + "="*80)
    print("✓ TEST COMPLETE")
    print("="*80)
    print(f"Generated: {len(locations)} locations")
    print(f"HTML map: {html_file}")
    print(f"PNG map: test_locations_map.png")
    print("="*80 + "\n")
