"""Inherits base classes in executor.py for multiprocessing."""

import multiprocessing
import signal
from multiprocessing.pool import ExceptionWithTraceback

from .executor import (BaseAsyncPoolExecutor, BaseWorkerManager,
                       BaseWorkerMixin, ResultItem)

__all__ = ['ProcessAsyncPoolExecutor']


class _ProcessWorker(BaseWorkerMixin, multiprocessing.Process):

    def __init__(self, *args, **kwargs):
        # Not to use pipe for the sake of ForkingPickler in SimpleQueue.
        self._submit_queue = multiprocessing.SimpleQueue()

        super().__init__(*args, **kwargs)

    def run(self):
        # Ignore SIGINT as worker processes should be closed by executor.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        super().run()

    def _make_picklable(self, stuff):
        if isinstance(stuff, BaseException) and stuff.__traceback__:
            return ExceptionWithTraceback(stuff, stuff.__traceback__)
        return stuff


class _ProcessWorkerManager(BaseWorkerManager):

    _Worker = _ProcessWorker

    def __init__(self, *args, **kwargs):
        # All process workers share a common result queue. Not for
        # submit queue.
        self._result_queue = multiprocessing.SimpleQueue()

        super().__init__(*args, **kwargs)

        # For listening result queue pipe reader and child process sentinel.
        self._listeners = [self._result_queue._reader]
        for worker in self._workers:
            self._listeners.append(worker.sentinel)

    def wait_return_item(self) -> ResultItem:
        ready = multiprocessing.connection.wait(self._listeners)
        if self._result_queue._reader not in ready:
            # Process will put CLOSING to result queue right before
            # it closes and thus be removed from listening list. If not,
            # process does not closed in the right way.
            raise ConnectionAbortedError()
        return self._result_queue._reader.recv()  # No need the read lock.

    def remove_closed_worker(self, worker_id):
        target = super().remove_closed_worker(worker_id)
        self._listeners.remove(target.sentinel)


class ProcessAsyncPoolExecutor(BaseAsyncPoolExecutor):
    _WorkerManager = _ProcessWorkerManager
