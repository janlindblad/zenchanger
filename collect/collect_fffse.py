
import datetime, json, requests
from core.models import Event, Country, Organization
from .collect_base import Collector
from .models import Record

class Collect_fffse(Collector):
    def __init__(self, source):
        super().__init__(source)
        self.responses = []
      
    def collect_data(self):
        print(f"fffse collect_data() for source {self.source.id} {self.source.url}")
        token = self.source.settings.get('token', None)
        url = self.source.url
        response = requests.get(f'{url}{token}')
        response_text = response.text
        response_text = response_text[response_text.find('['):response_text.rfind(']')+1]
        response_list = json.loads(response_text)
        response_count = len(response_list)
        print(f"fffse collected {response_count} responses")
        self.responses = response_list
        self.report(f"Collected {len(self.responses)} items")
        return True

    def clear_data(self):
        print(f"fffse clear_data() for source {self.source.id}")
        cleared_count = Event.objects.filter(ext_data_src=self.source.id).count()
        Event.objects.filter(ext_data_src=self.source.id).delete()
        print(f"fffse cleared {cleared_count} events from {self.source.id}")
        self.report(f"Cleared {cleared_count} old events")
        return True

    def store_data(self):
        print(f"fffse store_data() for source {self.source.id} with {len(self.responses)} responses")
        stored_count = 0
        sweden = Country.objects.get(code='SE')
        fff_sweden = Organization.objects.get(name='Fridays For Future Sweden')
        for item in self.responses:
            print(f"     Response id {item['RTIME']} submitted at {datetime.datetime.utcfromtimestamp(item['RTIME'])}")
            try:
                event = Event.objects.create(
                    id = f'{self.source.id}:{item["RTIME"]}',
                    ext_data_src = self.source.id,
                    date = self.source.settings.get('date', '2020-09-25'),
                    country = sweden,
                )
                event.save()
                event.organizers.add(fff_sweden)
                stored_count += 1
                print(f"     Stored event: {event.id} at {event.date} in {event.location}")
            except Exception as e:
                print(f"     Error storing event: {e}")
                continue
        self.report(f"Stored {stored_count} new events")
        return True
    
    def report(self, result):
        Record.objects.create(
            source=self.source,
            result=result,
            timestamp=datetime.datetime.now()
        )

Collector.register('fffse', Collect_fffse)