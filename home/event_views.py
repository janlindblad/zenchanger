from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from core.models import Event, Country, Location, Organization, EventPlan
from datetime import date, datetime
import re

import logging
logger = logging.getLogger(__name__)

@login_required
def event_list_view(request):
    """List all events with filtering and pagination"""
    logger.info("Event list view called")
    
    try:
        events = Event.objects.select_related('country', 'location').prefetch_related('organizers').order_by('-date')
        logger.info(f"Found {events.count()} events")
        
        # Get event plans for the new section
        event_plans = EventPlan.objects.select_related(
            'location', 'country'
        ).prefetch_related('organizers').order_by('name')
        
        # Filtering (existing code for events)
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
            'event_plans': event_plans,  # Add this line
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
        return render(request, 'home/event_list.html', {
            'page_obj': None,
            'event_plans': EventPlan.objects.none(),  # Add this line
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
        
        # Enhanced validation with specific error messages
        errors = []
        
        # Validate date
        if not date_str:
            errors.append("Date is required")
        else:
            try:
                parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append("Date format is invalid")
        
        # Validate time
        if not time_of_day:
            errors.append("Time is required")
        elif not re.match(r'^\d{2}:\d{2}$', time_of_day):
            errors.append("Time format is invalid (must be HH:MM)")
        
        # Validate location
        if not location_id:
            errors.append("Location is required")
        else:
            try:
                location = Location.objects.get(id=location_id)
            except (Location.DoesNotExist, ValueError):
                errors.append("Selected location is invalid")
        
        # If there are validation errors, show them specifically
        if errors:
            for error in errors:
                messages.error(request, f"Validation error: {error}")
        else:
            try:
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
                    date=parsed_date,
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
        location_id = request.POST.get('location')
        time_of_day = request.POST.get('time_of_day')
        organizer_ids = request.POST.getlist('organizers')
        
        # Enhanced validation with specific error messages
        errors = []
        
        # Validate date
        if not date_str:
            errors.append("Date is required")
        else:
            try:
                parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append("Date format is invalid")
        
        # Validate time
        if not time_of_day:
            errors.append("Time is required")
        elif not re.match(r'^\d{2}:\d{2}$', time_of_day):
            errors.append("Time format is invalid (must be HH:MM)")
        
        # Validate location
        if not location_id:
            errors.append("Location is required")
        else:
            try:
                location = Location.objects.get(id=location_id)
            except (Location.DoesNotExist, ValueError):
                errors.append("Selected location is invalid")
        
        # If there are validation errors, show them specifically
        if errors:
            for error in errors:
                messages.error(request, f"Validation error: {error}")
        else:
            try:
                # Get location and auto-set country
                location = Location.objects.get(id=location_id)
                country = location.in_country
                
                # Update event
                event.date = parsed_date
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
        'can_edit': can_edit,
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
    query = request.GET.get('q', '').strip()
    locations = Location.objects.filter(
        name__icontains=query
    ).select_related('in_country')[:10]
    
    location_data = [{
        'id': loc.id,
        'name': loc.name.title(),
        'country': loc.in_country.name.title(),
        'display': f"{loc.name.title()} ({loc.in_country.name.title()})",
        'full_name': loc.full_name()  # Add this line
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

# Update the eventplan_create_view function

@login_required
def eventplan_create_view(request):
    """Create a new event plan"""
    if request.method == 'POST':
        # ... existing POST logic remains the same ...
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        location_id = request.POST.get('location')
        expected_participants = request.POST.get('expected_participants')
        organizer_ids = request.POST.getlist('organizers')
        weekday = request.POST.get('weekday')
        recurrence = request.POST.get('recurrence')
        recur_from = request.POST.get('recur_from')
        recur_until = request.POST.get('recur_until')
        
        # Enhanced validation with specific error messages
        errors = []
        
        # Validate name
        if not name or not name.strip():
            errors.append("Plan name is required")
        
        # Validate location
        if not location_id:
            errors.append("Location is required")
        else:
            try:
                location = Location.objects.get(id=location_id)
            except (Location.DoesNotExist, ValueError):
                errors.append("Selected location is invalid")
        
        # Validate expected participants if provided
        if expected_participants:
            try:
                expected_participants = int(expected_participants)
                if expected_participants <= 0:
                    errors.append("Expected participants must be a positive number")
            except ValueError:
                errors.append("Expected participants must be a valid number")
        else:
            expected_participants = None
        
        # Validate recurrence logic
        if recurrence and recurrence != 'irregular':
            if not weekday:
                errors.append("Weekday must be specified for recurring events")
        
        # Validate date range
        if recur_from:
            try:
                recur_from_date = datetime.strptime(recur_from, '%Y-%m-%d').date()
            except ValueError:
                errors.append("Start date format is invalid")
                recur_from_date = None
        else:
            recur_from_date = None
            
        if recur_until:
            try:
                recur_until_date = datetime.strptime(recur_until, '%Y-%m-%d').date()
            except ValueError:
                errors.append("End date format is invalid")
                recur_until_date = None
        else:
            recur_until_date = None
            
        if recur_from_date and recur_until_date and recur_from_date >= recur_until_date:
            errors.append("Start date must be before end date")
        
        # If there are validation errors, show them specifically
        if errors:
            for error in errors:
                messages.error(request, f"Validation error: {error}")
        else:
            try:
                # Get location and auto-set country
                location = Location.objects.get(id=location_id)
                country = location.in_country
                
                # Create event plan
                event_plan = EventPlan.objects.create(
                    name=name.strip(),
                    description=description.strip(),
                    location=location,
                    country=country,
                    expected_participants=expected_participants,
                    weekday=weekday if weekday else None,
                    recurrence=recurrence if recurrence else None,
                    recur_from=recur_from_date,
                    recur_until=recur_until_date,
                    created_by=request.user
                )
                
                # Add organizers
                if organizer_ids:
                    organizers = Organization.objects.filter(id__in=organizer_ids)
                    event_plan.organizers.set(organizers)
                
                messages.success(request, f'Event plan "{event_plan.name}" created successfully.')
                return redirect('eventplan_detail', plan_id=event_plan.id)
                
            except Exception as e:
                messages.error(request, f'Error creating event plan: {str(e)}')
    
    # Get form data
    organizations = Organization.objects.order_by('name')
    
    # Calculate month later date
    from datetime import timedelta
    today = date.today()
    month_later = today + timedelta(days=30)  # Approximate month
    
    return render(request, 'home/eventplan_create.html', {
        'organizations': organizations,
        'today': today.isoformat(),
        'month_later': month_later.isoformat(),  # Add this line
        'weekday_choices': EventPlan.Weekday.choices,
        'recurrence_choices': EventPlan.Recurrence.choices,
    })
@login_required
def eventplan_detail_view(request, plan_id):
    """View event plan details"""
    event_plan = get_object_or_404(EventPlan, id=plan_id)
    
    # Check if user can edit/delete
    can_edit = request.user.is_staff or request.user == event_plan.created_by or request.user.stakeholder_organizations.filter(
        organization__in=event_plan.organizers.all()
    ).exists()
    
    # Get upcoming event dates if it's a recurring plan
    upcoming_dates = []
    if event_plan.recurrence and event_plan.recurrence != 'irregular':
        upcoming_dates = event_plan.get_next_event_dates(10)
    
    return render(request, 'home/eventplan_detail.html', {
        'event_plan': event_plan,
        'can_edit': can_edit,
        'upcoming_dates': upcoming_dates,
    })

@login_required
def eventplan_edit_view(request, plan_id):
    """Edit an existing event plan"""
    event_plan = get_object_or_404(EventPlan, id=plan_id)
    
    # Check permissions
    can_edit = request.user.is_staff or request.user == event_plan.created_by or request.user.stakeholder_organizations.filter(
        organization__in=event_plan.organizers.all()
    ).exists()
    
    if not can_edit:
        messages.error(request, 'You do not have permission to edit this event plan.')
        return redirect('eventplan_detail', plan_id=event_plan.id)
    
    if request.method == 'POST':
        # Similar validation logic as create view
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        location_id = request.POST.get('location')
        expected_participants = request.POST.get('expected_participants')
        organizer_ids = request.POST.getlist('organizers')
        weekday = request.POST.get('weekday')
        recurrence = request.POST.get('recurrence')
        recur_from = request.POST.get('recur_from')
        recur_until = request.POST.get('recur_until')
        
        # Validation logic (same as create)
        errors = []
        
        if not name or not name.strip():
            errors.append("Plan name is required")
        
        if not location_id:
            errors.append("Location is required")
        else:
            try:
                location = Location.objects.get(id=location_id)
            except (Location.DoesNotExist, ValueError):
                errors.append("Selected location is invalid")
        
        if expected_participants:
            try:
                expected_participants = int(expected_participants)
                if expected_participants <= 0:
                    errors.append("Expected participants must be a positive number")
            except ValueError:
                errors.append("Expected participants must be a valid number")
        else:
            expected_participants = None
        
        if recurrence and recurrence != 'irregular':
            if not weekday:
                errors.append("Weekday must be specified for recurring events")
        
        # Date validation
        if recur_from:
            try:
                recur_from_date = datetime.strptime(recur_from, '%Y-%m-%d').date()
            except ValueError:
                errors.append("Start date format is invalid")
                recur_from_date = None
        else:
            recur_from_date = None
            
        if recur_until:
            try:
                recur_until_date = datetime.strptime(recur_until, '%Y-%m-%d').date()
            except ValueError:
                errors.append("End date format is invalid")
                recur_until_date = None
        else:
            recur_until_date = None
            
        if recur_from_date and recur_until_date and recur_from_date >= recur_until_date:
            errors.append("Start date must be before end date")
        
        if errors:
            for error in errors:
                messages.error(request, f"Validation error: {error}")
        else:
            try:
                location = Location.objects.get(id=location_id)
                country = location.in_country
                
                # Update event plan
                event_plan.name = name.strip()
                event_plan.description = description.strip()
                event_plan.location = location
                event_plan.country = country
                event_plan.expected_participants = expected_participants
                event_plan.weekday = weekday if weekday else None
                event_plan.recurrence = recurrence if recurrence else None
                event_plan.recur_from = recur_from_date
                event_plan.recur_until = recur_until_date
                event_plan.save()
                
                # Update organizers
                if organizer_ids:
                    organizers = Organization.objects.filter(id__in=organizer_ids)
                    event_plan.organizers.set(organizers)
                else:
                    event_plan.organizers.clear()
                
                messages.success(request, f'Event plan "{event_plan.name}" updated successfully.')
                return redirect('eventplan_detail', plan_id=event_plan.id)
                
            except Exception as e:
                messages.error(request, f'Error updating event plan: {str(e)}')
    
    organizations = Organization.objects.order_by('name')
    
    return render(request, 'home/eventplan_edit.html', {
        'event_plan': event_plan,
        'organizations': organizations,
        'can_edit': can_edit,
        'weekday_choices': EventPlan.Weekday.choices,
        'recurrence_choices': EventPlan.Recurrence.choices,
    })

@login_required
def eventplan_delete_view(request, plan_id):
    """Delete an event plan"""
    event_plan = get_object_or_404(EventPlan, id=plan_id)
    
    # Check permissions
    can_delete = request.user.is_staff or request.user == event_plan.created_by or request.user.stakeholder_organizations.filter(
        organization__in=event_plan.organizers.all()
    ).exists()
    
    if not can_delete:
        messages.error(request, 'You do not have permission to delete this event plan.')
        return redirect('eventplan_detail', plan_id=event_plan.id)
    
    if request.method == 'POST':
        plan_name = event_plan.name
        event_plan.delete()
        messages.success(request, f'Event plan "{plan_name}" deleted successfully.')
        return redirect('event_list')
    
    return render(request, 'home/eventplan_delete.html', {'event_plan': event_plan})