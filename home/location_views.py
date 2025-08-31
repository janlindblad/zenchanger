import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from collect.google_maps_api import google_maps_lookup, create_location_with_chain
from core.models import Location, Country

@login_required
def location_create_view(request):
    """Create a new location using Google Maps lookup"""
    if request.method == 'POST':
        search_query = request.POST.get('search_query', '').strip()
        selected_result = request.POST.get('selected_result')
        
        if not search_query:
            messages.error(request, 'Please enter a location name to search.')
            return redirect('location_create')
        
        if selected_result:
            # User has selected a specific result from multiple options
            try:
                result_data = json.loads(selected_result)
                return process_location_creation(request, result_data, search_query)
            except (json.JSONDecodeError, KeyError) as e:
                messages.error(request, f'Invalid location data: {e}')
                return redirect('location_create')
        else:
            # Initial search - perform Google Maps lookup
            lookup_result = google_maps_lookup(search_query)
            
            if lookup_result['status'] == 'error':
                messages.error(request, f"Location lookup failed: {lookup_result['message']}")
                return render(request, 'home/location_create.html', {
                    'search_query': search_query
                })
            
            results = lookup_result['results']
            
            if not results:
                messages.error(request, f"No results found for '{search_query}'. Please try a different search term.")
                return render(request, 'home/location_create.html', {
                    'search_query': search_query
                })
            
            if len(results) == 1:
                # Single result - proceed directly
                return process_location_creation(request, results[0], search_query)
            else:
                # Multiple results - let user choose
                return render(request, 'home/location_create.html', {
                    'search_query': search_query,
                    'results': results,
                    'show_results': True
                })
    
    return render(request, 'home/location_create.html')

def process_location_creation(request, result_data, search_query):
    """Process the creation of a location from Google Maps result"""
    try:
        # Extract country code from address components
        country_code = None
        for component in result_data.get('address_components', []):
            if 'country' in component.get('types', []):
                country_code = component.get('short_name', '').lower()
                break
        
        if not country_code:
            messages.error(request, 'Could not determine country from location data.')
            return redirect('location_create')
        
        # Check if country exists in our database
        try:
            country = Country.objects.get(code=country_code)
        except Country.DoesNotExist:
            messages.error(request, f'Country "{country_code.upper()}" is not in our database. Please contact an administrator.')
            return redirect('location_create')
        
        # Create location chain
        location_chain = result_data.get('location_chain', [])
        if not location_chain:
            # Fallback to using the search query as location name
            location_chain = [search_query]
        
        created_locations = create_location_with_chain(
            country_code=country_code,
            location_chain=location_chain,
            lat=result_data.get('lat', 0.0),
            lon=result_data.get('lon', 0.0)
        )
        
        if created_locations:
            messages.success(request, f'Successfully created location(s): {", ".join(created_locations)}')
            
            # Find the most specific location that was created
            final_location = Location.objects.filter(
                name__iexact=location_chain[-1].lower(),
                in_country=country
            ).first()
            
            # If we came from event creation/editing, return the location data
            if request.GET.get('return_json'):
                return JsonResponse({
                    'success': True,
                    'location': {
                        'id': final_location.id if final_location else None,
                        'name': final_location.name.title() if final_location else location_chain[-1],
                        'country': country.name.title(),
                        'display': f"{final_location.name.title()} ({country.name.title()})" if final_location else f"{location_chain[-1]} ({country.name.title()})"
                    }
                })
        else:
            messages.info(request, 'Location already exists in the database.')
        
        return redirect('location_create')
        
    except Exception as e:
        messages.error(request, f'Error creating location: {str(e)}')
        return redirect('location_create')

@login_required
def location_search_popup(request):
    """Handle location search in a popup/modal context"""
    search_query = request.GET.get('q', '').strip()
    
    if not search_query:
        return JsonResponse({'error': 'No search query provided'})
    
    # First check if location already exists
    existing_locations = Location.objects.filter(
        name__icontains=search_query
    ).select_related('in_country')[:5]
    
    existing_data = [{
        'id': loc.id,
        'name': loc.name.title(),
        'country': loc.in_country.name.title(),
        'display': f"{loc.name.title()} ({loc.in_country.name.title()})",
        'exists': True
    } for loc in existing_locations]
    
    # If no exact matches, suggest creating new location
    if not existing_locations or not any(loc.name.lower() == search_query.lower() for loc in existing_locations):
        existing_data.insert(0, {
            'id': 'new',
            'name': f'Create new location: {search_query}',
            'display': f'🔍 Create new location: {search_query}',
            'search_query': search_query,
            'exists': False
        })
    
    return JsonResponse({'suggestions': existing_data})

@login_required 
@require_POST
def location_quick_create(request):
    """Quick location creation via AJAX"""
    search_query = request.POST.get('search_query', '').strip()
    
    if not search_query:
        return JsonResponse({'error': 'No search query provided'})
    
    # Perform Google Maps lookup
    lookup_result = google_maps_lookup(search_query)
    
    if lookup_result['status'] == 'error':
        return JsonResponse({'error': lookup_result['message']})
    
    results = lookup_result['results']
    
    if not results:
        return JsonResponse({'error': f"No results found for '{search_query}'"})
    
    if len(results) == 1:
        # Single result - create immediately
        try:
            result_data = results[0]
            
            # Extract country code
            country_code = None
            for component in result_data.get('address_components', []):
                if 'country' in component.get('types', []):
                    country_code = component.get('short_name', '').lower()
                    break
            
            if not country_code:
                return JsonResponse({'error': 'Could not determine country from location data'})
            
            # Check if country exists
            try:
                country = Country.objects.get(code=country_code)
            except Country.DoesNotExist:
                return JsonResponse({'error': f'Country "{country_code.upper()}" is not in our database'})
            
            # Create location
            location_chain = result_data.get('location_chain', [search_query])
            created_locations = create_location_with_chain(
                country_code=country_code,
                location_chain=location_chain,
                lat=result_data.get('lat', 0.0),
                lon=result_data.get('lon', 0.0)
            )
            
            # Find the created location
            final_location = Location.objects.filter(
                name__iexact=location_chain[-1].lower(),
                in_country=country
            ).first()
            
            return JsonResponse({
                'success': True,
                'location': {
                    'id': final_location.id,
                    'name': final_location.name.title(),
                    'country': country.name.title(),
                    'display': f"{final_location.name.title()} ({country.name.title()})"
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': f'Error creating location: {str(e)}'})
    
    else:
        # Multiple results - return them for user to choose
        return JsonResponse({
            'multiple_results': True,
            'results': results,
            'search_query': search_query
        })