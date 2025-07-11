import os, requests
from core.models import Location, Country

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
    
def create_location_with_chain(country_code, location_chain, lat, lon):
    """
    Create Location objects based on Google Maps result data
    """
    
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
    return created_locations

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

