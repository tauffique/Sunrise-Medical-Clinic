import threading


class ChangeBus:
    """Tells waiting listeners (the live-update stream) when an appointment changes."""

    def __init__(self):
        self._cond = threading.Condition()
        self._version = 0

    @property
    def version(self):
        with self._cond:
            return self._version

    def publish(self):
        with self._cond:
            self._version += 1
            self._cond.notify_all()

    def wait_for_change(self, last_seen, timeout=25):
        with self._cond:
            self._cond.wait_for(lambda: self._version != last_seen, timeout=timeout)
            return self._version != last_seen
