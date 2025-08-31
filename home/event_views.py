from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from core.models import Event, Country, Location, Organization
from datetime import date

import logging
logger = logging.getLogger(__name__)

# Add this to the top of your event_views.py to help debug
import logging
logger = logging.getLogger(__name__)

@login_required
def event_list_view(request):
    """List all events with filtering and pagination"""
    logger.info("Event list view called")
    
    try:
        events = Event.objects.select_related('country', 'location').prefetch_related('organizers').order_by('-date')
        logger.info(f"Found {events.count()} events")
        
        # Filtering
        country_filter = request.GET.get('country')
        location_filter = request.GET.get('location')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        search = request.GET.get('search')
        
        if country_filter:
            events = events.filter(country__code=country_filter)
        
        if location_filter:
            events = events.filter(location__id=location_filter)
        
        if date_from:
            events = events.filter(date__gte=date_from)
        
        if date_to:
            events = events.filter(date__lte=date_to)
        
        if search:
            events = events.filter(
                Q(id__icontains=search) |
                Q(country__name__icontains=search) |
                Q(location__name__icontains=search)
            )
        
        # Pagination
        paginator = Paginator(events, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get filter options
        countries = Country.objects.filter(visibility=Country.Visibility.DEFAULT).order_by('name')
        locations = Location.objects.order_by('name')
        
        logger.info(f"Rendering template with {page_obj.object_list.count()} events on page")
        
        return render(request, 'home/event_list.html', {
            'page_obj': page_obj,
            'countries': countries,
            'locations': locations,
            'current_filters': {
                'country': country_filter,
                'location': location_filter,
                'date_from': date_from,
                'date_to': date_to,
                'search': search,
            }
        })
    except Exception as e:
        logger.error(f"Error in event_list_view: {e}")
        # Return a simple error page for debugging
        return render(request, 'home/event_list.html', {
            'page_obj': None,
            'countries': [],
            'locations': [],
            'current_filters': {},
            'error': str(e)
        })
@login_required
def event_create_view(request):
    """Create a new event"""
    if request.method == 'POST':
        date_str = request.POST.get('date')
        location_id = request.POST.get('location')
        time_of_day = request.POST.get('time_of_day')
        organizer_ids = request.POST.getlist('organizers')
        
        try:
            # Validate required fields
            if not all([date_str, location_id, time_of_day]):
                messages.error(request, 'Please fill in all required fields.')
                return redirect('event_create')
            
            # Get location and auto-set country
            location = Location.objects.get(id=location_id)
            country = location.in_country
            
            # Generate auto-incremented event ID
            last_gc_event = Event.objects.filter(id__startswith='gc:').order_by('-id').first()
            if last_gc_event:
                last_number = int(last_gc_event.id.split(':')[1])
                new_number = last_number + 1
            else:
                new_number = 1
            
            event_id = f"gc:{new_number}"
            
            # Check if event ID already exists (shouldn't happen, but safety check)
            while Event.objects.filter(id=event_id).exists():
                new_number += 1
                event_id = f"gc:{new_number}"
            
            # Create event
            event = Event.objects.create(
                id=event_id,
                ext_data_src="gc",
                date=date_str,
                country=country,
                location=location,
                time_of_day=time_of_day
            )
            
            # Add organizers
            if organizer_ids:
                organizers = Organization.objects.filter(id__in=organizer_ids)
                event.organizers.set(organizers)
            
            messages.success(request, f'Event "{event_id}" created successfully.')
            return redirect('event_detail', event_id=event.id)
            
        except Location.DoesNotExist:
            messages.error(request, 'Selected location does not exist.')
        except Exception as e:
            messages.error(request, f'Error creating event: {str(e)}')
    
    # Get form data
    organizations = Organization.objects.order_by('name')
    
    # Generate preview event ID
    last_gc_event = Event.objects.filter(id__startswith='gc:').order_by('-id').first()
    if last_gc_event:
        next_number = int(last_gc_event.id.split(':')[1]) + 1
    else:
        next_number = 1
    preview_event_id = f"gc:{next_number}"
    
    return render(request, 'home/event_create.html', {
        'organizations': organizations,
        'today': date.today().isoformat(),
        'preview_event_id': preview_event_id,
    })

@login_required
def event_detail_view(request, event_id):
    """View event details"""
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user can edit/delete (example logic - adjust as needed)
    can_edit = request.user.is_staff or request.user.stakeholder_organizations.filter(
        organization__in=event.organizers.all()
    ).exists()
    
    return render(request, 'home/event_detail.html', {
        'event': event,
        'can_edit': can_edit,
    })

@login_required
def event_edit_view(request, event_id):
    """Edit an existing event"""
    event = get_object_or_404(Event, id=event_id)
    
    # Check permissions
    can_edit = request.user.is_staff or request.user.stakeholder_organizations.filter(
        organization__in=event.organizers.all()
    ).exists()
    
    if not can_edit:
        messages.error(request, 'You do not have permission to edit this event.')
        return redirect('event_detail', event_id=event.id)
    
    if request.method == 'POST':
        date_str = request.POST.get('date')
        country_code = request.POST.get('country')
        location_id = request.POST.get('location')
        time_of_day = request.POST.get('time_of_day')
        organizer_ids = request.POST.getlist('organizers')
        
        try:
            # Validate required fields
            if not all([date_str, country_code, time_of_day]):
                messages.error(request, 'Please fill in all required fields.')
                return redirect('event_edit', event_id=event.id)
            
            # Get related objects
            country = Country.objects.get(code=country_code)
            location = None
            if location_id:
                location = Location.objects.get(id=location_id)
            
            # Update event
            event.date = date_str
            event.country = country
            event.location = location
            event.time_of_day = time_of_day
            event.save()
            
            # Update organizers
            if organizer_ids:
                organizers = Organization.objects.filter(id__in=organizer_ids)
                event.organizers.set(organizers)
            else:
                event.organizers.clear()
            
            messages.success(request, f'Event "{event.id}" updated successfully.')
            return redirect('event_detail', event_id=event.id)
            
        except Country.DoesNotExist:
            messages.error(request, 'Selected country does not exist.')
        except Location.DoesNotExist:
            messages.error(request, 'Selected location does not exist.')
        except Exception as e:
            messages.error(request, f'Error updating event: {str(e)}')
    
    # Get form data
    countries = Country.objects.filter(visibility=Country.Visibility.DEFAULT).order_by('name')
    organizations = Organization.objects.order_by('name')
    locations_in_country = Location.objects.filter(in_country=event.country).order_by('name')
    
    return render(request, 'home/event_edit.html', {
        'event': event,
        'countries': countries,
        'organizations': organizations,
        'locations_in_country': locations_in_country,
    })

@login_required
def event_delete_view(request, event_id):
    """Delete an event"""
    event = get_object_or_404(Event, id=event_id)
    
    # Check permissions
    can_delete = request.user.is_staff or request.user.stakeholder_organizations.filter(
        organization__in=event.organizers.all()
    ).exists()
    
    if not can_delete:
        messages.error(request, 'You do not have permission to delete this event.')
        return redirect('event_detail', event_id=event.id)
    
    if request.method == 'POST':
        event_id_copy = event.id
        event.delete()
        messages.success(request, f'Event "{event_id_copy}" deleted successfully.')
        return redirect('event_list')
    
    return render(request, 'home/event_delete.html', {'event': event})

@login_required
def location_events_view(request, location_id):
    """View events in a specific location"""
    location = get_object_or_404(Location, id=location_id)
    
    events = Event.objects.filter(location=location).select_related('country').prefetch_related('organizers').order_by('-date')
    
    # Pagination
    paginator = Paginator(events, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'home/location_events.html', {
        'location': location,
        'page_obj': page_obj,
    })

# AJAX helper view for getting locations by country
@login_required
def get_locations_by_country(request):
    """Get locations for a specific country (AJAX)"""
    country_code = request.GET.get('country')
    if country_code:
        locations = Location.objects.filter(in_country__code=country_code).order_by('name')
        location_data = [{'id': loc.id, 'name': loc.name.title()} for loc in locations]
        return JsonResponse({'locations': location_data})
    return JsonResponse({'locations': []})

@login_required
def search_locations(request):
    """Search locations by name (AJAX)"""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'locations': []})
    
    locations = Location.objects.filter(
        name__icontains=query
    ).select_related('in_country').order_by('name')[:20]
    
    location_data = [{
        'id': loc.id,
        'name': loc.name.title(),
        'country': loc.in_country.name.title(),
        'country_code': loc.in_country.code,
        'display': f"{loc.name.title()} ({loc.in_country.name.title()})"
    } for loc in locations]
    
    return JsonResponse({'locations': location_data})

@login_required
def search_organizations(request):
    """Search organizations by name (AJAX)"""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'organizations': []})
    
    organizations = Organization.objects.filter(
        name__icontains=query
    ).order_by('name')[:20]
    
    org_data = [{
        'id': org.id,
        'name': org.name
    } for org in organizations]
    
    return JsonResponse({'organizations': org_data})