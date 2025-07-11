import os
from django.shortcuts import render, get_object_or_404
from core.models import Country, Location
import requests

def location_view(request):
    locations = Location.objects.select_related('in_country', 'in_location').all()
    
    # Apply filter for zero coordinates if checkbox is checked
    filter_zero_coords = request.GET.get('filter_zero_coords')
    if filter_zero_coords:
        locations = locations.filter(lat=0.0, lon=0.0)
    
    # Build location chain for each location
    location_data = []
    for location in locations:
        chain = []
        current = location.in_location
        depth = 0
        while current and depth < 10:
            chain.append(current.name.title())
            current = current.in_location
            depth += 1
        
        location_data.append({
            'location': location,
            'chain': ', '.join(chain) if chain else '-'
        })
    
    return render(request, 'collect/location_view.html', {
        'location_data': location_data,
        'filter_zero_coords': filter_zero_coords
    })

def location_detail(request, pk):
    location = get_object_or_404(Location, id=pk)
    
    # Build location chain
    chain = []
    current = location.in_location
    depth = 0
    while current and depth < 10:
        chain.append(current)
        current = current.in_location
        depth += 1
    
    # Get sub-locations
    sublocations = location.sublocations.all()
    
    # Get events at this location
    events = location.events.all()
    
    # Handle Google Maps lookup
    google_result = None
    create_message = None
    
    if request.method == 'POST':
        if 'lookup' in request.POST:
            google_result = google_maps_lookup(location.name)
            
            # Process each result to determine what locations need to be created
            if google_result and google_result.get('status') == 'success':
                for i, result in enumerate(google_result['results']):
                    missing_locations = []
                    coordinate_updates = []
                    
                    # Find country code from address components
                    country_code = None
                    components = result.get('address_components', [])
                    for component in components:
                        if 'country' in component['types']:
                            country_code = component['short_name']
                            break
                    
                    # Check each location in the chain
                    print(f"Looking for country code {country_code}")
                    for j, loc_name in enumerate(result['location_chain']):
                        if country_code:
                            if j == len(result['location_chain']) - 1:
                                # Last one, check country table instead
                                existing_country = Country.objects.filter(code=country_code).first()
                                if not existing_country:
                                    create_message = f"Country '{country_code}' not found in database"
                                    break
                                continue
                            
                            existing_loc = Location.objects.filter(
                                name__iexact=loc_name.lower(),
                                in_country__code=country_code
                            ).first()
                            
                            if not existing_loc:
                                missing_locations.append(loc_name)
                            elif j == 0:  # Only check coordinates for the most specific location
                                # Check if coordinates differ significantly (>50 meters)
                                google_lat, google_lon = result['lat'], result['lon']
                                print(f"Checking coordinates for {existing_loc.name}: ({existing_loc.lat}, {existing_loc.lon}) vs ({google_lat}, {google_lon})")
                                if coordinates_differ_significantly(existing_loc.lat, existing_loc.lon, google_lat, google_lon):
                                    coordinate_updates.append({
                                        'location': existing_loc,
                                        'current_lat': existing_loc.lat,
                                        'current_lon': existing_loc.lon,
                                        'google_lat': google_lat,
                                        'google_lon': google_lon
                                    })
                    
                    # Add the missing locations and coordinate updates info to the result
                    result['missing_locations'] = missing_locations
                    result['coordinate_updates'] = coordinate_updates
                    result['country_code'] = country_code
                    result['create_button_id'] = f"create_{i}"
                    
        elif 'create_locations' in request.POST:
            try:
                create_message = create_locations_from_google_result(request.POST)
            except Exception as e:
                create_message = f"Error creating locations: {str(e)}"
                
        elif 'update_coordinates' in request.POST:
            try:
                create_message = update_location_coordinates(request.POST)
            except Exception as e:
                create_message = f"Error updating coordinates: {str(e)}"
    
    return render(request, 'collect/location_detail.html', {
        'location': location,
        'chain': chain,
        'sublocations': sublocations,
        'events': events,
        'google_result': google_result,
        'create_message': create_message
    })

def google_maps_lookup(location_name):
    """
    Perform Google Maps geocoding lookup for a location name.
    Returns dict with lat, lon, and address components.
    """
    # If the location_name contains a :, the last part is the 
    # location within the city and should go first
    location_name_parts = location_name.split(":")
    location_name_parts.reverse() 
    location_name = ', '.join(location_name_parts).strip()
    try:
        # You'll need to set your Google Maps API key
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        url = f"https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            'address': location_name,
            'key': api_key
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data['status'] == 'OK' and data['results']:
            print(f"Google Maps lookup for '{location_name}' returned {len(data['results'])} results")
            
            # Process all results
            results = []
            for i, result in enumerate(data['results']):
                geometry = result['geometry']['location']
                
                # Extract address components for location chain
                components = result.get('address_components', [])
                # Always keep the first component as the main location
                location_chain = [components[0]['long_name']] if components else []
                # Add other relevant components to the chain
                for component in components[1:]:
                    if any(t in ['postal_town','locality', 'country'] 
                           for t in component['types']):
                        location_chain.append(component['long_name'])
                
                results.append({
                    'lat': geometry['lat'],
                    'lon': geometry['lng'],
                    'formatted_address': result['formatted_address'],
                    'location_chain': location_chain,
                    'place_id': result.get('place_id', ''),
                    'types': result.get('types', []),
                    'address_components': components,
                })
            
            return {
                'status': 'success',
                'results': results,
                'total_results': len(results)
            }
        else:
            return {'status': 'error', 'message': f"No results found for '{location_name}'"}
            
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
    

def create_locations_from_google_result(post_data):
    """
    Create Location objects based on Google Maps result data
    """
    from core.models import Location, Country
    
    # Extract data from POST
    country_code = post_data.get('country_code')
    location_chain = post_data.getlist('location_chain')  # List of location names
    lat = float(post_data.get('lat', 0))
    lon = float(post_data.get('lon', 0))
    
    # Verify country exists
    try:
        country = Country.objects.get(code=country_code)
    except Country.DoesNotExist:
        raise ValueError(f"Country with code '{country_code}' not found in database")
    
    created_locations = []
    parent_location = None
    
    # Create locations in reverse order (country -> city -> street)
    for i, loc_name in enumerate(reversed(location_chain)):
        # Check if location already exists
        existing = Location.objects.filter(
            name__iexact=loc_name.lower(),
            in_country=country
        ).first()
        
        if existing:
            parent_location = existing
        else:
            # Create new location
            new_location = Location.objects.create(
                name=loc_name.lower(),
                in_country=country,
                in_location=parent_location,
                lat=lat if i == len(location_chain) - 1 else 0.0,  # Only first location gets real coordinates
                lon=lon if i == len(location_chain) - 1 else 0.0
            )
            created_locations.append(new_location.name.title())
            parent_location = new_location
    
    if created_locations:
        return f"Successfully created locations: {', '.join(created_locations)}"
    else:
        return "All locations already exist in database"


def coordinates_differ_significantly(lat1, lon1, lat2, lon2, threshold_meters=50):
    """
    Check if two coordinate pairs differ by more than threshold_meters using Haversine formula
    """
    import math
    
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in meters
    r = 6371000
    distance = c * r
    
    return distance > threshold_meters

def update_location_coordinates(post_data):
    """
    Update Location coordinates based on Google Maps data
    """
    from core.models import Location
    
    location_id = post_data.get('location_id')
    new_lat = float(post_data.get('new_lat'))
    new_lon = float(post_data.get('new_lon'))
    
    try:
        location = Location.objects.get(id=location_id)
        old_lat, old_lon = location.lat, location.lon
        location.lat = new_lat
        location.lon = new_lon
        location.save()
        
        return f"Updated coordinates for '{location.name.title()}' from ({old_lat}, {old_lon}) to ({new_lat}, {new_lon})"
    except Location.DoesNotExist:
        raise ValueError(f"Location with ID {location_id} not found")


# Example data:
# Google Maps lookup for 'barkarby' returned:
# [{
#   'address_components': [
#     {'long_name': 'Barkarby', 'short_name': 'Barkarby', 'types': ['political', 'sublocality', 'sublocality_level_1']}, 
#     {'long_name': 'Stockholm County', 'short_name': 'Stockholm County', 'types': ['administrative_area_level_1', 'political']}, 
#     {'long_name': 'Sweden',  'short_name': 'SE', 'types': ['country', 'political']}, 
#   ], 
#   'formatted_address': 'Barkarby, Sweden', 
#   'geometry': {
#     'bounds': {'northeast': {'lat': 59.426904, 'lng': 17.8953599}, 'southwest': {'lat': 59.3908569, 'lng': 17.8504171}}, 
#     'location': {'lat': 59.4001312, 'lng': 17.8625101}, 
#     'location_type': 'APPROXIMATE', 
#     'viewport': {'northeast': {'lat': 59.426904, 'lng': 17.8953599}, 'southwest': {'lat': 59.3908569, 'lng': 17.8504171}}
#   }, 
#   'place_id': 'ChIJi8TipAyfX0YRRs9UWDo_adU', 
#   'types': ['political', 'sublocality', 'sublocality_level_1']
# }]


# Google Maps lookup for 'mynttorget, stockholm' returned:
# [{
#   'address_components': [
#     {'long_name': 'Mynttorget', 'short_name': 'Mynttorget', 'types': ['route']}, 
#     {'long_name': 'Södermalm', 'short_name': 'Södermalm', 'types': ['political', 'sublocality', 'sublocality_level_1']}, 
#     {'long_name': 'Stockholm', 'short_name': 'Stockholm', 'types': ['postal_town']}, 
#     {'long_name': 'Stockholms län', 'short_name': 'Stockholms län', 'types': ['administrative_area_level_1', 'political']}, 
#     {'long_name': 'Sweden', 'short_name': 'SE', 'types': ['country', 'political']}, 
#     {'long_name': '111 28', 'short_name': '111 28', 'types': ['postal_code']}
#   ],
#   'formatted_address': 'Mynttorget, 111 28 Stockholm, Sweden', 
#   'geometry': {
#     'bounds': {'northeast': {'lat': 59.3270857, 'lng': 18.0695183}, 'southwest': {'lat': 59.3265189, 'lng': 18.0683749}}, 
#     'location': {'lat': 59.3266528, 'lng': 18.0689832}, 
#     'location_type': 'GEOMETRIC_CENTER', 
#     'viewport': {'northeast': {'lat': 59.3281512802915, 'lng': 18.0702955802915}, 'southwest': {'lat': 59.32545331970849, 'lng': 18.0675976197085}}
#   }, 
#   'place_id': 'ChIJPyUNpFidX0YR4bUQ0wTbXuY', 
#   'types': ['route']
# }]
