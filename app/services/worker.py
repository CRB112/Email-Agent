"""One background thread and persistent asyncio loop; callbacks run on drain()."""

import asyncio
import inspect
from queue import Empty, Queue
from threading import Thread


class BackgroundWorker:
    def __init__(self):
        self.jobs = Queue()
        self.events = Queue()
        self.closed = False
        self.resources = []
        self.thread = Thread(target=self._run, name="mail-worker", daemon=True)
        self.thread.start()

    def register_resource(self, resource):
        self.resources.append(resource)
        return resource

    def submit(self, operation, on_success, on_error, on_progress=None):
        if self.closed:
            raise RuntimeError("Worker is closed")
        self.jobs.put((operation, on_success, on_error, on_progress))

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            while (job := self.jobs.get()) is not None:
                operation, success, error, progress = job

                def report(*args):
                    if progress is not None:
                        self.events.put((progress, args))

                try:
                    result = operation(report)
                    if inspect.isawaitable(result):
                        result = loop.run_until_complete(result)
                except Exception as exception:
                    self.events.put((error, (exception,)))
                else:
                    self.events.put((success, (result,)))
        finally:
            for resource in self.resources:
                try:
                    result = resource.close()
                    if inspect.isawaitable(result):
                        loop.run_until_complete(result)
                except Exception:
                    # Cleanup must not prevent remaining sessions from closing.
                    import logging
                    logging.getLogger(__name__).exception("Could not close mailbox session")
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    def drain(self):
        # Called only by the Tk thread. No worker code touches widgets.
        for _ in range(100):
            try:
                callback, args = self.events.get_nowait()
            except Empty:
                break
            callback(*args)

    def close(self):
        if not self.closed:
            self.closed = True
            self.jobs.put(None)
