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

# City configurations
CITIES = {
    'toronto': {
        'name': 'Toronto',
        'center': {'lat': 43.6452, 'lng': -79.3806},  # Union Station
        'center_name': 'Union Station',
        'radius_km': 10,
        'radius_meters': 10000
    },
    'san-francisco': {
        'name': 'San Francisco',
        'center': {'lat': 37.7749, 'lng': -122.4194},  # Downtown SF
        'center_name': 'Downtown',
        'radius_km': 10,
        'radius_meters': 10000
    }
}

# Default city
DEFAULT_CITY = 'toronto'

# Backwards compatibility - Toronto Union Station coordinates
UNION_STATION = CITIES['toronto']['center']
MAX_RADIUS_KM = CITIES['toronto']['radius_km']
MAX_RADIUS_METERS = CITIES['toronto']['radius_meters']


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


def get_nearby_subway_stations(center_lat, center_lng, radius_meters=10000):
    """
    Get subway/metro stations within a given radius using Places API.
    Returns list of station coordinates.
    """
    try:
        # Use Places API to find transit stations
        places_result = gmaps.places_nearby(
            location=(center_lat, center_lng),
            radius=radius_meters,
            type='subway_station'
        )

        stations = []
        if places_result.get('results'):
            for place in places_result['results']:
                location = place['geometry']['location']
                stations.append({
                    'lat': location['lat'],
                    'lng': location['lng'],
                    'name': place.get('name', 'Unknown Station')
                })

        return stations
    except Exception as e:
        print(f"Warning: Could not fetch subway stations: {e}")
        return []


def generate_biased_origin(city_config):
    """
    Generate origin with bias toward transit stations or city center proximity.
    - 60% chance: Within 500m of a subway/transit station
    - 20% chance: Within 3km of city center
    - 20% chance: Anywhere in city radius
    """
    center = city_config['center']
    radius_meters = city_config['radius_meters']
    center_name = city_config['center_name']

    rand = random.random()

    if rand < 0.6:
        # Try to get near transit station
        try:
            stations = get_nearby_subway_stations(
                center['lat'],
                center['lng'],
                radius_meters
            )

            if stations:
                # Pick random station and generate point within 500m
                station = random.choice(stations)
                origin_lat, origin_lng = generate_random_point_in_radius(
                    station['lat'],
                    station['lng'],
                    500  # 500m radius around station
                )
                print(f"  → Generated origin near transit station: {station['name']}")
                return origin_lat, origin_lng
        except Exception as e:
            print(f"  → Transit station selection failed, falling back to random: {e}")

    if rand < 0.8:
        # Within 3km of city center
        origin_lat, origin_lng = generate_random_point_in_radius(
            center['lat'],
            center['lng'],
            3000  # 3km radius
        )
        print(f"  → Generated origin near {center_name} (< 3km)")
        return origin_lat, origin_lng

    # Anywhere in city radius
    origin_lat, origin_lng = generate_random_point_in_radius(
        center['lat'],
        center['lng'],
        radius_meters
    )
    print(f"  → Generated origin anywhere in {city_config['radius_km']}km radius")
    return origin_lat, origin_lng


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
    Pick random origin and destination within a city's radius
    and return ETAs for all travel modes.
    Only returns locations accessible by all four transport modes.
    Excludes routes that require ferry rides.
    Ensures walking time between origin and destination is at least 30 minutes.

    Query parameters:
    - city: City identifier (e.g., 'toronto', 'san-francisco'). Defaults to 'toronto'.
    """
    from flask import request

    # Get city from query parameter, default to Toronto
    city_id = request.args.get('city', DEFAULT_CITY)

    # Validate city
    if city_id not in CITIES:
        return jsonify({
            'error': f'Invalid city: {city_id}. Available cities: {list(CITIES.keys())}'
        }), 400

    city_config = CITIES[city_id]
    center = city_config['center']
    radius_meters = city_config['radius_meters']

    print(f"\n🌆 Generating game for {city_config['name']}")

    max_attempts = 30  # Try up to 30 times to find valid origin/destination pair

    for attempt in range(max_attempts):
        try:
            # Generate biased origin (prefer transit stations or city center proximity)
            origin_lat, origin_lng = generate_biased_origin(city_config)

            origin = {
                'lat': origin_lat,
                'lng': origin_lng
            }

            # Check if origin is on water - skip if it is
            if is_on_water(origin):
                print(f"✗ Attempt {attempt + 1}: Skipping - origin is on water")
                continue

            # Generate random destination
            dest_lat, dest_lng = generate_random_point_in_radius(
                center['lat'],
                center['lng'],
                radius_meters
            )

            destination = {
                'lat': dest_lat,
                'lng': dest_lng
            }

            # Check if destination is on water - skip if it is
            if is_on_water(destination):
                print(f"✗ Attempt {attempt + 1}: Skipping - destination is on water")
                continue

            # Check if route requires ferry - skip if it does
            if has_ferry_in_route(origin, destination):
                print(f"✗ Attempt {attempt + 1}: Skipping - requires ferry")
                continue

            # Get ETAs for all modes
            etas = get_etas(origin, destination)

            # Check if all four modes are available (no errors)
            required_modes = ['driving', 'transit', 'bicycling', 'walking']
            all_modes_available = all(
                mode in etas and 'error' not in etas[mode]
                for mode in required_modes
            )

            if not all_modes_available:
                missing_modes = [m for m in required_modes if m not in etas or 'error' in etas[m]]
                print(f"✗ Attempt {attempt + 1}: Skipping - missing modes: {missing_modes}")
                continue

            # Check walking time is at least 30 minutes
            walking_duration_text = etas['walking'].get('duration', '')
            # Extract minutes from duration text (e.g., "32 mins" or "1 hour 5 mins")
            walking_minutes = 0
            if 'hour' in walking_duration_text:
                hours = int(walking_duration_text.split()[0])
                walking_minutes += hours * 60
                if 'min' in walking_duration_text:
                    mins = int(walking_duration_text.split()[-2])
                    walking_minutes += mins
            elif 'min' in walking_duration_text:
                walking_minutes = int(walking_duration_text.split()[0])

            if walking_minutes < 30:
                print(f"✗ Attempt {attempt + 1}: Skipping - walking time only {walking_minutes} mins (need 30+)")
                continue

            # Get human-readable addresses
            origin_address = get_address(origin_lat, origin_lng)
            destination_address = get_address(dest_lat, dest_lng)

            print(f"✓ Found valid origin/destination pair on attempt {attempt + 1} (walking: {walking_minutes} mins)")
            return jsonify({
                'origin': origin,
                'origin_address': origin_address,
                'destination': destination,
                'destination_address': destination_address,
                'etas': etas
            })

        except Exception as e:
            print(f"✗ Attempt {attempt + 1}: Error - {str(e)}")
            continue

    # If we couldn't find a valid origin/destination pair after max_attempts
    return jsonify({
        'error': f'Could not find origin/destination pair with all transport modes and 30+ min walk after {max_attempts} attempts'
    }), 500


@app.route('/cities', methods=['GET'])
def get_cities():
    """
    Get list of available cities with their configurations.
    """
    cities_list = []
    for city_id, config in CITIES.items():
        cities_list.append({
            'id': city_id,
            'name': config['name'],
            'center': config['center'],
            'centerName': config['center_name'],
            'radiusKm': config['radius_km']
        })
    return jsonify({
        'cities': cities_list,
        'default': DEFAULT_CITY
    })


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
@app.route('/toronto', methods=['GET'])
@app.route('/san-francisco', methods=['GET'])
@app.route('/sf', methods=['GET'])
def index():
    """
    Serve the main HTML page for all city routes.
    Routes:
    - / (defaults to Toronto)
    - /toronto
    - /san-francisco
    - /sf (alias for San Francisco)
    """
    from flask import send_file
    import os

    # Check if index.html exists in the current directory
    index_path = os.path.join(os.path.dirname(__file__), 'index.html')

    if os.path.exists(index_path):
        return send_file(index_path)
    else:
        # Fallback to API response if index.html not found
        return jsonify({
            'message': 'ETA Guesser API',
            'endpoints': {
                '/random-destination': 'Get random destination and ETAs (supports ?city=toronto or ?city=san-francisco)',
                '/cities': 'Get list of available cities',
                '/maps-api-key': 'Get Google Maps API key for frontend'
            }
        })


if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 ETA Guesser Backend Starting...")
    print("="*80)
    print(f"🌆 Available cities:")
    for city_id, config in CITIES.items():
        print(f"   • {config['name']}: {config['center_name']} ({config['radius_km']}km radius)")
    print(f"🎯 Only destinations with all 4 transport modes")
    print(f"⛴️  Ferry routes excluded")
    print(f"🌐 Server: http://localhost:5001")
    print("="*80 + "\n")

    app.run(debug=True, port=5001)
