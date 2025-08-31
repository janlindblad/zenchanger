import uuid
from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords

class Country(models.Model):
    class Visibility(models.TextChoices):
        DEFAULT = "DEFT", "Default"
        NODETAILS = "NODE", "NoDetails"
        HIDDEN = "HIDE", "Hidden"

    code = models.CharField(max_length=3, primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    visibility = models.CharField(
        max_length=4,
        choices=Visibility.choices,
        default=Visibility.DEFAULT
    )
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        self.name = self.name.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name.title()}"

class Location(models.Model):
    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255, blank=True)
    in_country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='locations')
    in_location = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='sublocations')
    lat = models.FloatField()
    lon = models.FloatField()
    history = HistoricalRecords()

    class Meta:
        unique_together = ('name', 'in_location')

    def save(self, *args, **kwargs):
        self.name = self.name.lower()
        super().save(*args, **kwargs)

    def full_name(self):
        """
        Return the full hierarchical name of the location with country at the end.
        Example: "Barkarby, Järfälla Kommun, Stockholms Län, Sweden"
        """
        # Build the location chain from most specific to least specific
        location_chain = []
        current_location = self
        
        # Traverse up the location hierarchy
        while current_location:
            location_chain.append(current_location.name.title())
            current_location = current_location.in_location
        
        # Add country name at the end
        location_chain.append(self.in_country.name.title())
        
        # Join with commas and return
        return ', '.join(location_chain)

    def __str__(self):
        return f"{self.name.title()} ({self.in_country.code})"

class Organization(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.SET_NULL)
    history = HistoricalRecords()

    def __str__(self):
        return self.name

class Role(models.Model):
    name = models.CharField(max_length=255)
    history = HistoricalRecords()

    def __str__(self):
        return self.name

class Stakeholder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stakeholder_organizations')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='stakeholders')
    role = models.ForeignKey('Role', on_delete=models.CASCADE, related_name='stakeholders')
    history = HistoricalRecords()

    class Meta:
        unique_together = ('user', 'organization', 'role')

    def __str__(self):
        return f"{self.user.username} - {self.role.name} @ {self.organization.name}"

class EventPlan(models.Model):
    class Weekday(models.TextChoices):
        MONDAY = "MON", "Monday"
        TUESDAY = "TUE", "Tuesday"
        WEDNESDAY = "WED", "Wednesday"
        THURSDAY = "THU", "Thursday"
        FRIDAY = "FRI", "Friday"
        SATURDAY = "SAT", "Saturday"
        SUNDAY = "SUN", "Sunday"

    class Recurrence(models.TextChoices):
        IRREGULAR = "irregular", "Irregular"
        WEEKLY = "weekly", "Weekly"
        MONTHLY_FIRST = "monthly-first", "Monthly (1st weekday)"
        MONTHLY_SECOND = "monthly-second", "Monthly (2nd weekday)"
        MONTHLY_THIRD = "monthly-third", "Monthly (3rd weekday)"
        MONTHLY_LAST = "monthly-last", "Monthly (last weekday)"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    expected_participants = models.PositiveIntegerField(null=True, blank=True)
    time_of_day = models.CharField(max_length=5)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='event_plans')
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='event_plans')
    organizers = models.ManyToManyField(Organization, related_name='event_plans')
    
    # New recurrence fields
    weekday = models.CharField(
        max_length=3,
        choices=Weekday.choices,
        null=True,
        blank=True,
        help_text="Day of the week for recurring events"
    )
    recurrence = models.CharField(
        max_length=15,
        choices=Recurrence.choices,
        null=True,
        blank=True,
        help_text="How often the event recurs"
    )
    recur_from = models.DateField(
        null=True,
        blank=True,
        help_text="Start date for recurring events"
    )
    recur_until = models.DateField(
        null=True,
        blank=True,
        help_text="End date for recurring events"
    )
    
    created_by = models.ForeignKey(User, null=True, on_delete=models.CASCADE, related_name='event_plans')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def __str__(self):
        recurrence_info = ""
        if self.recurrence and self.weekday:
            recurrence_info = f" ({self.get_recurrence_display()} on {self.get_weekday_display()}s)"
        return f"{self.name}{recurrence_info}"

    def clean(self):
        """Validate recurrence fields"""
        from django.core.exceptions import ValidationError
        
        # If recurrence is set (and not irregular), weekday should be set
        if self.recurrence and self.recurrence != self.Recurrence.IRREGULAR and not self.weekday:
            raise ValidationError("Weekday must be specified for recurring events")
        
        # If recur_until is set, recur_from should also be set
        if self.recur_until and not self.recur_from:
            raise ValidationError("Start date (recur_from) must be set if end date (recur_until) is specified")
        
        # recur_from should be before recur_until
        if self.recur_from and self.recur_until and self.recur_from >= self.recur_until:
            raise ValidationError("Start date must be before end date for recurring events")

    def get_next_event_dates(self, count=10):
        """
        Generate the next 'count' event dates based on recurrence pattern.
        Returns a list of date objects.
        """
        if not self.recurrence or self.recurrence == self.Recurrence.IRREGULAR:
            return []
        
        if not self.recur_from or not self.weekday:
            return []
        
        from datetime import datetime, timedelta
        import calendar
        
        dates = []
        current_date = self.recur_from
        weekday_num = list(self.Weekday.values).index(self.weekday)  # 0=Monday, 6=Sunday
        
        while len(dates) < count and (not self.recur_until or current_date <= self.recur_until):
            if self.recurrence == self.Recurrence.WEEKLY:
                # Find next occurrence of the weekday
                days_ahead = weekday_num - current_date.weekday()
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                next_date = current_date + timedelta(days_ahead)
                
            elif self.recurrence.startswith('monthly'):
                # Monthly recurrence patterns
                year = current_date.year
                month = current_date.month
                
                if self.recurrence == self.Recurrence.MONTHLY_FIRST:
                    week_num = 1
                elif self.recurrence == self.Recurrence.MONTHLY_SECOND:
                    week_num = 2
                elif self.recurrence == self.Recurrence.MONTHLY_THIRD:
                    week_num = 3
                elif self.recurrence == self.Recurrence.MONTHLY_LAST:
                    week_num = -1  # Last occurrence
                
                # Find the specific weekday occurrence in the month
                if week_num > 0:
                    # First, second, or third occurrence
                    first_day = datetime(year, month, 1).date()
                    first_weekday = (weekday_num - first_day.weekday()) % 7
                    target_day = 1 + first_weekday + (week_num - 1) * 7
                else:
                    # Last occurrence
                    last_day = calendar.monthrange(year, month)[1]
                    last_date = datetime(year, month, last_day).date()
                    days_back = (last_date.weekday() - weekday_num) % 7
                    target_day = last_day - days_back
                
                try:
                    next_date = datetime(year, month, target_day).date()
                except ValueError:
                    # Target day doesn't exist in this month, skip to next month
                    if month == 12:
                        current_date = datetime(year + 1, 1, 1).date()
                    else:
                        current_date = datetime(year, month + 1, 1).date()
                    continue
            
            if next_date >= current_date and (not self.recur_until or next_date <= self.recur_until):
                dates.append(next_date)
            
            # Move to next period
            if self.recurrence == self.Recurrence.WEEKLY:
                current_date = next_date + timedelta(days=1)
            else:  # Monthly
                if current_date.month == 12:
                    current_date = datetime(current_date.year + 1, 1, 1).date()
                else:
                    current_date = datetime(current_date.year, current_date.month + 1, 1).date()
        
        return dates

class Event(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    cancelled = models.BooleanField(default=False)
    ext_data_src = models.CharField(max_length=255, null=True, blank=True)
    plan = models.ForeignKey(EventPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name='events')
    date = models.DateField()
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='events')
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL, related_name='events')
    time_of_day = models.CharField(max_length=5)
    organizers = models.ManyToManyField(Organization, related_name='events')
    created_by = models.ForeignKey(User, null=True, on_delete=models.CASCADE, related_name='events_created')
    history = HistoricalRecords()

    @staticmethod
    def get_unique_id(prefix):
        return f"{prefix}:{uuid.uuid4().hex[:8]}"

    def __str__(self):
        loc = f", {self.location}" if self.location else ""
        return f"Event on {self.date}{loc} in {self.country.code}"

class EventRecord(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='records')
    timestamp = models.DateTimeField(auto_now_add=True)
    participants = models.PositiveIntegerField(null=True, blank=True)
    data = models.JSONField()

    def __str__(self):
        return f"Record for {self.event.id} at {self.timestamp}"
