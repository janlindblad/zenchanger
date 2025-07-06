import datetime

class Collector:
    _registry = {}

    @classmethod
    def register(cls, name, collector_class):
        cls._registry[name] = collector_class

    @classmethod
    def get(cls, name):
        return cls._registry.get(name)

    @staticmethod
    def dispatch(source, ops=["collect", "clear", "store"]):
        """
        Dispatches the collection process for the given source.
        """
        collector_class = Collector.get(source.plugin)
        if not collector_class:
            raise ValueError(f"No collector registered for plugin: {source.plugin}")
        
        collector = collector_class(source)
        if "collect" in ops:
            if not collector.collect_data():
                raise ValueError(f"{source.id} collection failed")
        if "clear" in ops:
            if not collector.clear_data():
                raise ValueError(f"{source.id} clearing failed")
        if "store" in ops:
            if not collector.store_data():
                raise ValueError(f"{source.id} storing failed")
            source.last_run = datetime.datetime.now(tz=datetime.timezone.utc)
            source.save()
        return True
    
    def __init__(self, source):
        self.source = source

    def collect_data(self):
        return True

    def clear_data(self):
        return True

    def store_data(self, response_list):
        return True
