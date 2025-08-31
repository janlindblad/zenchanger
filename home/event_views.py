from datetime import datetime, date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from core.models import Event, Country, Location, Organization, EventPlan                
from .utils import add_status_to_events

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
        
        # Filtering (existing filtering code)
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
        
        # Add status information using utility function
        events_with_status = add_status_to_events(events)
        
        # Pagination on the enriched data
        paginator = Paginator(events_with_status, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Get filter options
        countries = Country.objects.filter(visibility=Country.Visibility.DEFAULT).order_by('name')
        locations = Location.objects.order_by('name')
        
        logger.info(f"Rendering template with {len(page_obj.object_list)} events on page")
        
        return render(request, 'home/event_list.html', {
            'page_obj': page_obj,
            'event_plans': event_plans,
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
            'event_plans': EventPlan.objects.none(),
            'countries': [],
            'locations': [],
            'current_filters': {},
            'error': str(e)
        })

def generate_time_options():
    """Generate time options for select dropdown"""
    options = []
    for hour in range(24):
        for minute in [0, 30]:
            time_str = f"{hour:02d}:{minute:02d}"
            display_str = f"{hour:02d}:{minute:02d}"
            options.append((time_str, display_str))
    return options

@login_required
def event_create_view(request):
    """Create a new event"""
    # Get pre-filled location from URL parameter
    prefill_location_id = request.GET.get('location')
    prefill_location = None
    
    # Get pre-filled data from EventPlan
    prefill_plan_id = request.GET.get('plan')
    prefill_date_str = request.GET.get('date')  # Get as string first
    prefill_plan = None
    prefill_date = None
    prefill_date_display = None
    
    # Parse the prefill date if provided
    if prefill_date_str:
        try:
            prefill_date = datetime.strptime(prefill_date_str, '%Y-%m-%d').date()
            prefill_date_display = prefill_date.strftime('%A, %B %d, %Y')  # "Monday, January 1, 2024"
        except ValueError:
            prefill_date = None
            prefill_date_str = None
    
    if prefill_location_id:
        try:
            prefill_location = Location.objects.get(id=prefill_location_id)
        except (Location.DoesNotExist, ValueError):
            prefill_location = None
    
    if prefill_plan_id:
        try:
            prefill_plan = EventPlan.objects.get(id=prefill_plan_id)
            # If no location was specified but we have a plan, use plan's location
            if not prefill_location:
                prefill_location = prefill_plan.location
        except (EventPlan.DoesNotExist, ValueError):
            prefill_plan = None
    
    if request.method == 'POST':
        event_date_str = request.POST.get('date')
        time_of_day = request.POST.get('time_of_day')
        location_id = request.POST.get('location')
        organizer_ids = request.POST.getlist('organizers')
        plan_id = request.POST.get('plan')
        expected_participants = request.POST.get('expected_participants')
        
        # Enhanced validation with specific error messages
        errors = []
        
        # Validate date
        if not event_date_str:
            errors.append("Date is required")
        else:
            try:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append("Date format is invalid")
                event_date = None
        
        # Validate time
        if not time_of_day:
            errors.append("Time is required")
        else:
            try:
                event_time = datetime.strptime(time_of_day, '%H:%M').time()
            except ValueError:
                errors.append("Time format is invalid")
                event_time = None
        
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
                expected_participants_int = int(expected_participants)
                if expected_participants_int <= 0:
                    errors.append("Expected participants must be a positive number")
            except ValueError:
                errors.append("Expected participants must be a valid number")
                expected_participants_int = None
        else:
            expected_participants_int = None
        
        # If there are validation errors, show them specifically
        if errors:
            for error in errors:
                messages.error(request, f"Validation error: {error}")
        else:
            try:
                # Get location and auto-set country
                location = Location.objects.get(id=location_id)
                country = location.in_country
                
                # Get plan if specified
                plan = None
                if plan_id:
                    try:
                        plan = EventPlan.objects.get(id=plan_id)
                    except EventPlan.DoesNotExist:
                        pass
                
                # Generate a unique event ID
                event_id = Event.get_unique_id("gc")
                                
                # Create event with explicit ID
                event = Event.objects.create(
                    id=event_id,
                    date=event_date,
                    time_of_day=time_of_day,
                    location=location,
                    country=country,
                    plan=plan,
                    created_by=request.user
                )
                
                # Add organizers
                if organizer_ids:
                    organizers = Organization.objects.filter(id__in=organizer_ids)
                    event.organizers.set(organizers)
                
                messages.success(request, f'Event {event.id} created successfully.')
                return redirect('event_detail', event_id=event.id)
                
            except Exception as e:
                messages.error(request, f'Error creating event: {str(e)}')
    
    # Get form data
    organizations = Organization.objects.order_by('name')
    time_options = generate_time_options()
    
    # Prepare default values
    default_time = None
    default_expected_participants = None
    default_organizers = []
    
    if prefill_plan:
        default_time = prefill_plan.time_of_day
        default_expected_participants = prefill_plan.expected_participants
        default_organizers = list(prefill_plan.organizers.all())
    
    # Determine the default date value for the input field
    default_date_value = None
    if prefill_date_str:
        default_date_value = prefill_date_str  # Use the original string format YYYY-MM-DD
    elif request.POST.get('date'):
        default_date_value = request.POST.get('date')
    else:
        default_date_value = date.today().isoformat()
    
    # Handle expected participants default (for template input field)
    default_expected_participants_value = None
    if default_expected_participants:
        default_expected_participants_value = str(default_expected_participants)
    elif request.POST.get('expected_participants'):
        default_expected_participants_value = request.POST.get('expected_participants')
    else:
        default_expected_participants_value = ""
    
    return render(request, 'home/event_create.html', {
        'organizations': organizations,
        'time_options': time_options,
        'today': date.today().isoformat(),
        'prefill_location': prefill_location,
        'prefill_plan': prefill_plan,
        'prefill_date_str': prefill_date_str,
        'prefill_date_display': prefill_date_display,
        'default_date_value': default_date_value,
        'default_time': default_time,
        'default_expected_participants': default_expected_participants,  # For display in help text
        'default_expected_participants_value': default_expected_participants_value,  # For input field
        'default_organizers': default_organizers,
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
    
    if request.method == 'POST':
        event_date_str = request.POST.get('date')
        time_of_day = request.POST.get('time_of_day')
        location_id = request.POST.get('location')
        organizer_ids = request.POST.getlist('organizers')
        
        # Enhanced validation with specific error messages
        errors = []
        
        # Validate date
        if not event_date_str:
            errors.append("Date is required")
        else:
            try:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append("Date format is invalid")
                event_date = None
        
        # Validate time
        if not time_of_day:
            errors.append("Time is required")
        else:
            try:
                event_time = datetime.strptime(time_of_day, '%H:%M').time()
            except ValueError:
                errors.append("Time format is invalid")
                event_time = None
        
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
                event.date = event_date
                event.time_of_day = time_of_day
                event.location = location
                event.country = country
                event.save()
                
                # Update organizers
                if organizer_ids:
                    organizers = Organization.objects.filter(id__in=organizer_ids)
                    event.organizers.set(organizers)
                else:
                    event.organizers.clear()
                
                messages.success(request, f'Event {event.id} updated successfully.')
                return redirect('event_detail', event_id=event.id)
                
            except Exception as e:
                messages.error(request, f'Error updating event: {str(e)}')
    
    # Get form data
    organizations = Organization.objects.order_by('name')
    time_options = generate_time_options()  # Add this line
    
    # Handle form field defaults (for validation errors)
    form_defaults = {
        'date': request.POST.get('date', event.date.isoformat()),
        'time_of_day': request.POST.get('time_of_day', event.time_of_day),
    }
    
    return render(request, 'home/event_edit.html', {
        'event': event,
        'organizations': organizations,
        'time_options': time_options,  # Add this line
        'form_defaults': form_defaults,  # Add this line
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
    
    # Get event plans for this location
    event_plans = EventPlan.objects.filter(
        location=location
    ).select_related('location', 'country').prefetch_related('organizers').order_by('name')
    
    # Add status information using utility function
    events_with_status = add_status_to_events(events)
    
    # Pagination
    paginator = Paginator(events_with_status, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'home/location_events.html', {
        'location': location,
        'page_obj': page_obj,
        'event_plans': event_plans,
    })

# Add this view if it doesn't exist

@login_required
def country_events_view(request, country_code):
    """View events in a specific country"""
    country = get_object_or_404(Country, code=country_code)
    
    events = Event.objects.filter(country=country).select_related('country', 'location').prefetch_related('organizers').order_by('-date')
    
    # Add status information using utility function
    events_with_status = add_status_to_events(events)
    
    # Pagination
    paginator = Paginator(events_with_status, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'home/country_events.html', {
        'country': country,
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

@login_required
def eventplan_create_view(request):
    """Create a new event plan"""
    # Get pre-filled location from URL parameter
    prefill_location_id = request.GET.get('location')
    prefill_location = None
    
    if prefill_location_id:
        try:
            prefill_location = Location.objects.get(id=prefill_location_id)
        except (Location.DoesNotExist, ValueError):
            prefill_location = None
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        time_of_day = request.POST.get('time_of_day', '')
        location_id = request.POST.get('location')
        expected_participants = request.POST.get('expected_participants')
        organizer_ids = request.POST.getlist('organizers')
        weekday = request.POST.get('weekday')
        recurrence = request.POST.get('recurrence')
        recur_from_str = request.POST.get('recur_from')
        recur_until_str = request.POST.get('recur_until')
        
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
        if recur_from_str:
            try:
                recur_from_date = datetime.strptime(recur_from_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append("Start date format is invalid")
                recur_from_date = None
        else:
            recur_from_date = None
            
        if recur_until_str:
            try:
                recur_until_date = datetime.strptime(recur_until_str, '%Y-%m-%d').date()
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
                    time_of_day=time_of_day,
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
    time_options = generate_time_options()
    
    # Calculate month later date
    today = date.today()
    month_later = today + timedelta(days=30)
    
    # Handle form field defaults for re-display on validation errors
    form_defaults = {
        'name': request.POST.get('name', ''),
        'description': request.POST.get('description', ''),
        'time_of_day': request.POST.get('time_of_day', ''),
        'expected_participants': request.POST.get('expected_participants', ''),
        'weekday': request.POST.get('weekday', ''),
        'recurrence': request.POST.get('recurrence', ''),
        'recur_from': request.POST.get('recur_from', today.isoformat()),  # Default to today
        'recur_until': request.POST.get('recur_until', month_later.isoformat()),  # Default to month later
    }
    
    return render(request, 'home/eventplan_create.html', {
        'organizations': organizations,
        'time_options': time_options,
        'today': today.isoformat(),
        'month_later': month_later.isoformat(),
        'weekday_choices': EventPlan.Weekday.choices,
        'recurrence_choices': EventPlan.Recurrence.choices,
        'prefill_location': prefill_location,
        'form_defaults': form_defaults,
    })

@login_required
def eventplan_detail_view(request, plan_id):
    """View details of a specific event plan"""
    event_plan = get_object_or_404(EventPlan, id=plan_id)
    
    # Get upcoming dates
    upcoming_dates = event_plan.get_next_event_dates(count=10)
    
    # Check for existing events on these dates
    upcoming_dates_with_status = []
    for date_obj in upcoming_dates:
        # Check if there's already an event for this plan on this date
        existing_event = Event.objects.filter(
            plan=event_plan,
            date=date_obj
        ).first()
        
        upcoming_dates_with_status.append({
            'date': date_obj,
            'existing_event': existing_event,
            'has_event': existing_event is not None,
            'is_cancelled': existing_event.cancelled if existing_event else False,
        })
    
    return render(request, 'home/eventplan_detail.html', {
        'event_plan': event_plan,
        'upcoming_dates': upcoming_dates,
        'upcoming_dates_with_status': upcoming_dates_with_status,
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

@login_required
def cancel_event_view(request, plan_id, date_str):
    """Cancel an event for a specific plan and date"""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('eventplan_detail', plan_id=plan_id)
    
    event_plan = get_object_or_404(EventPlan, id=plan_id)
    
    try:
        event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, 'Invalid date format.')
        return redirect('eventplan_detail', plan_id=plan_id)
    
    # Check if there's already an event (cancelled or not) for this date
    existing_event = Event.objects.filter(plan=event_plan, date=event_date).first()
    
    if existing_event:
        if existing_event.cancelled:
            messages.warning(request, f'Event for {event_date.strftime("%B %d, %Y")} is already cancelled.')
        else:
            # Mark existing event as cancelled
            existing_event.cancelled = True
            existing_event.save()
            messages.success(request, f'Event for {event_date.strftime("%B %d, %Y")} has been cancelled.')
    else:
        # Create a new cancelled event
        event_id = Event.get_unique_id("gc")
        
        Event.objects.create(
            id=event_id,
            plan=event_plan,
            date=event_date,
            time_of_day=event_plan.time_of_day,
            location=event_plan.location,
            country=event_plan.country,
            cancelled=True,
            created_by=request.user
        )
        
        # Add organizers from the plan
        cancelled_event = Event.objects.get(id=event_id)
        cancelled_event.organizers.set(event_plan.organizers.all())
        
        messages.success(request, f'Event for {event_date.strftime("%B %d, %Y")} has been cancelled.')
    
    return redirect('eventplan_detail', plan_id=plan_id)

@login_required
def uncancel_event_view(request, plan_id, date_str):
    """Remove cancellation from an event (delete the cancelled event record)"""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('eventplan_detail', plan_id=plan_id)
    
    event_plan = get_object_or_404(EventPlan, id=plan_id)
    
    try:
        event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, 'Invalid date format.')
        return redirect('eventplan_detail', plan_id=plan_id)
    
    # Find the cancelled event
    cancelled_event = Event.objects.filter(
        plan=event_plan, 
        date=event_date, 
        cancelled=True
    ).first()
    
    if cancelled_event:
        # Delete the cancelled event entirely to return to neutral state
        cancelled_event.delete()
        messages.success(request, f'Cancelled event for {event_date.strftime("%B %d, %Y")} has been removed. Date is now available for scheduling.')
    else:
        messages.warning(request, f'No cancelled event found for {event_date.strftime("%B %d, %Y")}.')
    
    return redirect('eventplan_detail', plan_id=plan_id)