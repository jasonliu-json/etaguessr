from flask import Flask, jsonify
from flask_cors import CORS
import googlemaps
import random
import math
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# Google Maps API key from environment variable
API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
if not API_KEY:
    raise ValueError(
        "GOOGLE_MAPS_API_KEY not found in environment variables. "
        "Set this server-side environment variable (e.g. on your host) "
        "or create a local .env file with GOOGLE_MAPS_API_KEY=your_key_here."
    )

# Shared Google Maps client, used for backend ETA / geocoding calls
gmaps = googlemaps.Client(key=API_KEY)

# Toronto Union Station coordinates
UNION_STATION = {
    'lat': 43.6452,
    'lng': -79.3806
}

# 25 km in meters (for distance calculations)
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
        # e.g., "Toronto, ON, Canada" vs "123 Main St, Toronto, ON, Canada"
        address_parts = [comp for comp in address_components
                        if any(t in comp.get('types', [])
                              for t in ['street_number', 'route'])]

        if not address_parts:
            # No street-level address components, likely water
            return True

        return False

    except Exception as e:
        print(f"Warning: Could not check if on water: {e}")
        # On error, assume it's not on water to avoid blocking valid locations
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


def get_etas(origin, destination):
    """
    Get ETAs for all travel modes from origin to destination.
    """
    modes = ['driving', 'transit', 'bicycling', 'walking']
    etas = {}

    print("\n" + "="*80)
    print(f"ROUTE: Union Station → Destination")
    print(f"Origin: {origin['lat']:.4f}, {origin['lng']:.4f}")
    print(f"Destination: {destination['lat']:.4f}, {destination['lng']:.4f}")
    print("="*80)

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

            if result['rows'][0]['elements'][0]['status'] == 'OK':
                element = result['rows'][0]['elements'][0]
                duration = element['duration']['text']
                distance = element['distance']['text']

                etas[mode] = {
                    'duration': duration,
                    'distance': distance,
                    'duration_seconds': element['duration']['value'],
                    'distance_meters': element['distance']['value']
                }

                # Print to console
                mode_emoji = {
                    'driving': '🚗',
                    'transit': '🚇',
                    'bicycling': '🚴',
                    'walking': '🚶'
                }
                print(f"{mode_emoji.get(mode, '•')} {mode.upper():12} - {duration:15} ({distance})")

            else:
                etas[mode] = {'error': 'Route not available'}
                print(f"• {mode.upper():12} - NOT AVAILABLE")

        except Exception as e:
            etas[mode] = {'error': str(e)}
            print(f"• {mode.upper():12} - ERROR: {str(e)}")

    print("="*80 + "\n")

    return etas


def get_address(lat, lng):
    """
    Get human-readable address from coordinates using reverse geocoding.
    """
    try:
        result = gmaps.reverse_geocode((lat, lng))
        if result:
            return result[0]['formatted_address']
        return f"{lat:.4f}, {lng:.4f}"
    except Exception as e:
        print(f"Error getting address: {e}")
        return f"{lat:.4f}, {lng:.4f}"


@app.route('/random-destination', methods=['GET'])
def random_destination():
    """
    Pick a random destination within 10 km of Union Station
    and return ETAs for all travel modes.
    Only returns destinations accessible by all four transport modes.
    Excludes destinations that require ferry rides.
    """
    max_attempts = 20  # Try up to 20 times to find a valid destination

    for attempt in range(max_attempts):
        try:
            # Generate random destination
            dest_lat, dest_lng = generate_random_point_in_radius(
                UNION_STATION['lat'],
                UNION_STATION['lng'],
                MAX_RADIUS_METERS
            )

            destination = {
                'lat': dest_lat,
                'lng': dest_lng
            }

            # Check if point is on water - skip if it is
            if is_on_water(destination):
                print(f"✗ Attempt {attempt + 1}: Skipping - point is on water")
                continue

            # Check if route requires ferry - skip if it does
            if has_ferry_in_route(UNION_STATION, destination):
                print(f"✗ Attempt {attempt + 1}: Skipping - requires ferry")
                continue

            # Get ETAs for all modes
            etas = get_etas(UNION_STATION, destination)

            # Check if all four modes are available (no errors)
            required_modes = ['driving', 'transit', 'bicycling', 'walking']
            all_modes_available = all(
                mode in etas and 'error' not in etas[mode]
                for mode in required_modes
            )

            if all_modes_available:
                # Get human-readable address
                destination_address = get_address(dest_lat, dest_lng)

                print(f"✓ Found valid destination on attempt {attempt + 1}")
                return jsonify({
                    'origin': UNION_STATION,
                    'destination': destination,
                    'destination_address': destination_address,
                    'etas': etas
                })
            else:
                # Skip this destination, try another
                missing_modes = [m for m in required_modes if m not in etas or 'error' in etas[m]]
                print(f"✗ Attempt {attempt + 1}: Skipping - missing modes: {missing_modes}")
                continue

        except Exception as e:
            print(f"✗ Attempt {attempt + 1}: Error - {str(e)}")
            continue

    # If we couldn't find a valid destination after max_attempts
    return jsonify({
        'error': f'Could not find a destination with all transport modes after {max_attempts} attempts'
    }), 500


@app.route('/maps-api-key', methods=['GET'])
def maps_api_key():
    """
    Lightweight endpoint to expose the Google Maps JS API key to the frontend.

    The key itself is sourced **only** from the server-side environment variable
    GOOGLE_MAPS_API_KEY, so deployments just need to set that env var and both
    backend and frontend will work.
    """
    return jsonify({'googleMapsApiKey': API_KEY})


@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'message': 'ETA Guesser API',
        'endpoints': {
            '/random-destination': 'Get random destination and ETAs from Union Station'
        }
    })


if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 ETA Guesser Backend Starting...")
    print("="*80)
    print(f"📍 Origin: Union Station, Toronto ({UNION_STATION['lat']}, {UNION_STATION['lng']})")
    print(f"📏 Max radius: {MAX_RADIUS_KM} km")
    print(f"🎯 Only destinations with all 4 transport modes")
    print(f"⛴️  Ferry routes excluded")
    print(f"🌐 Server: http://localhost:5001")
    print("="*80 + "\n")

    app.run(debug=True, port=5001)
