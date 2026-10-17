import threading

from app.models import AcceptRequest


class Service:

    def __init__(self):
        self.events: dict[str, AcceptRequest] = {}
        self.latest: dict[str, AcceptRequest] = {}
        self.lock = threading.Lock()

    def add(self, service: AcceptRequest) -> str:
        with self.lock:
            exist = self.events.get(service.event_id)
            if exist is not None:
                same = (
                    exist.sensor_id == service.sensor_id
                    and exist.value == service.value
                    and exist.observed_at == service.observed_at
                )
                what_return = ''
                if same:
                    what_return = 'duplicate'
                else:
                    what_return = 'conflict'
                return what_return

            self.events[service.event_id] = service

            current = self.latest.get(service.sensor_id)

            if current is None or service.observed_at > current.observed_at:
                self.latest[service.sensor_id] = service

            return 'accepted'

    def get_latest(self, sensor_id: str) -> AcceptRequest | None:
        with self.lock:
            return self.latest.get(sensor_id)

    def clear(self) -> None:
        with self.lock:
            self.events.clear()
            self.latest.clear()

