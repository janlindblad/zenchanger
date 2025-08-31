from datetime import date, timedelta

def get_event_status(event_obj):
    """
    Calculate the status of an event for UI display purposes.
    Returns one of: 'future', 'cancelled-future', 'recent-past', 'past'
    """
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    
    if event_obj.date > today:
        # Future event
        if getattr(event_obj, 'cancelled', False):
            return 'cancelled-future'
        else:
            return 'future'
    elif event_obj.date >= thirty_days_ago:
        # Past event within 30 days
        return 'recent-past'
    else:
        # Older past event
        return 'past'

def add_status_to_events(events_queryset):
    """
    Add status information to a queryset or list of events.
    Returns a list of dictionaries with 'event' and 'status' keys.
    """
    return [
        {
            'event': event,
            'status': get_event_status(event)
        }
        for event in events_queryset
    ]