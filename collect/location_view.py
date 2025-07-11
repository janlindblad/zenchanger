import os
from django.shortcuts import render, get_object_or_404
from core.models import Country, Location
from .google_maps_api import google_maps_lookup, create_location_with_chain, coordinates_differ_significantly

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
    
    created_locations = create_location_with_chain(country_code, location_chain, lat, lon)
    
    if created_locations:
        return f"Successfully created locations: {', '.join(created_locations)}"
    else:
        return "All locations already exist in database"

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
